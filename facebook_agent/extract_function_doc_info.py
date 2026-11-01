"""Extract structured information from the operation docstrings (description, parameters, output).

The docstrings follow the project convention (see README):

    Short description.

    Parameters:
        - Input-<name> (<type>, mandatory|optional): description
          Example: ...
          Choices:
              - value -> meaning
          Keys:                                  (sub-keys of a dict parameter)
              - Key-<name> (<type>, mandatory|optional): description
                Choices:
                    - value -> meaning

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", ...}
        Output type: ...
        Example (success): ...
        Errors: ...

Importing this module has no side effect (no request, no input). It does not build the
"tools" format of the LLM yet: that is the agentic phase.
"""
import importlib
import inspect
import pkgutil
import re
from typing import Callable

PARAM_LINE = re.compile(r"^-\s*Input-(\w+)\s*\(([^)]*)\)\s*:\s*(.*)$")
KEY_LINE = re.compile(r"^-\s*Key-(\w+)\s*\(([^)]*)\)\s*:\s*(.*)$")
CHOICE_LINE = re.compile(r"^-\s*(.+?)\s*(?:->|=>|→)\s*(.*)$")
EXAMPLE_MARKER = re.compile(r"^Examples?\s*:\s*(.*)$", re.IGNORECASE)
CHOICES_MARKER = re.compile(r"^(?:Choices?\b[^:]*|Supported formats)\s*:\s*(.*)$", re.IGNORECASE)
KEYS_MARKER = re.compile(r"^Keys\s*:\s*$", re.IGNORECASE)
OUTPUT_TYPE_MARKER = re.compile(r"^Output type\s*:\s*(.*)$", re.IGNORECASE)
SECTION = re.compile(r"^(Parameters|Returns)\s*:\s*$")
TYPE_ALIASES = {"integer": "int", "boolean": "bool", "string": "str", "double": "float"}


def _indent(line: str) -> int:
    """Number of leading spaces of a line."""
    return len(line) - len(line.lstrip(" "))


def _parse_declaration(declaration: str) -> tuple[str, bool]:
    """Split "str, mandatory" into ("str", True): the type alone, and the mandatory flag."""
    parts = [part.strip() for part in declaration.split(",")]
    raw_type = parts[0].lower()
    return TYPE_ALIASES.get(raw_type, raw_type), "mandatory" in [p.lower() for p in parts[1:]]


def _choice_value(line: str) -> str | None:
    """Value of a "- value -> meaning" line (quotes removed, case kept), or None."""
    match = CHOICE_LINE.match(line.strip())
    return match.group(1).strip().strip("\"'`") if match else None


def _split_sections(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (description lines, Parameters lines, Returns lines).

    A section starts only with a line that is exactly "Parameters:" or "Returns:" at the
    left margin, so a description that begins with "Returns ..." is not a section.
    """
    sections = {"description": [], "Parameters": [], "Returns": []}
    current = "description"
    for line in lines:
        match = SECTION.match(line) if _indent(line) == 0 else None
        if match:
            current = match.group(1)
            continue
        sections[current].append(line)
    return sections["description"], sections["Parameters"], sections["Returns"]


def _parse_item(lines: list[str], start: int, item_indent: int, first_desc: str) -> tuple[dict, int]:
    """Parse the lines under a parameter or a sub-key (deeper than item_indent).

    Return (info, index of the next line to read). info has desc, and if present example,
    choices and keys (for a dict parameter).
    """
    desc, example, choices, keys = [first_desc] if first_desc else [], [], [], {}
    mode, mode_indent = "desc", item_indent
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        indent, text = _indent(line), line.strip()
        if indent <= item_indent:
            break
        # Lignes plus indentées que le marqueur courant : elles appartiennent à ce marqueur
        if mode != "desc" and indent > mode_indent:
            if mode == "example":
                example.append(text)
            elif mode == "choices" and (value := _choice_value(text)) is not None:
                choices.append(value)
            elif mode == "keys" and (match := KEY_LINE.match(text)):
                key_type, key_required = _parse_declaration(match.group(2))
                key_info, index = _parse_item(lines, index + 1, indent, match.group(3).strip())
                keys[match.group(1)] = {"type": key_type, "required": key_required, **key_info}
                continue
            elif mode == "choices":
                desc.append(text)
            index += 1
            continue
        mode, mode_indent = "desc", indent
        if match := EXAMPLE_MARKER.match(text):
            mode = "example"
            if match.group(1):
                example.append(match.group(1))
        elif match := CHOICES_MARKER.match(text):
            mode = "choices"
            if match.group(1):  # valeurs sur la même ligne : "Choices: a, b"
                choices += [v.strip().strip("\"'`") for v in match.group(1).split(",") if v.strip()]
        elif KEYS_MARKER.match(text):
            mode = "keys"
        else:
            desc.append(text)
        index += 1
    info = {"desc": " ".join(desc).strip()}
    if example:
        info["example"] = " ".join(example).strip()
    if choices:
        info["choices"] = choices
    if keys:
        info["keys"] = keys
    return info, index


def _parse_parameters(lines: list[str]) -> tuple[dict, dict]:
    """Return (params, raw_params) from the lines of the Parameters section.

    Only the "- Input-<name>" lines at the indentation of the first one open a parameter:
    the "- Key-<name>" lines of a dict parameter are read as its sub-keys.
    """
    params, raw_params = {}, {}
    param_indent = next((_indent(line) for line in lines if PARAM_LINE.match(line.strip())), None)
    index = 0
    while index < len(lines):
        line = lines[index]
        match = PARAM_LINE.match(line.strip()) if _indent(line) == param_indent else None
        if not match:
            index += 1
            continue
        name = match.group(1)  # nom sans le préfixe Input-
        param_type, required = _parse_declaration(match.group(2))
        info, index = _parse_item(lines, index + 1, param_indent, match.group(3).strip())
        params[name] = {"type": param_type, "required": required, **info}
        raw_params[name] = line.strip()
    return params, raw_params


def _parse_returns(lines: list[str]) -> tuple[str, str | None]:
    """Return (text of the Returns section, Output type text or None)."""
    text = "\n".join(line.rstrip() for line in lines).strip()
    output_type = None
    for index, line in enumerate(lines):
        match = OUTPUT_TYPE_MARKER.match(line.strip())
        if match:
            parts = [match.group(1).strip()]
            for following in lines[index + 1:]:
                if not following.strip() or _indent(following) <= _indent(line):
                    break
                parts.append(following.strip())
            output_type = " ".join(part for part in parts if part)
            break
    return text, output_type


def check_signature(func: Callable, params: dict) -> list[str]:
    """Compare the documented parameters with the real signature of the function.

    Args:
        func: The documented function.
        params: Parameters extracted from its docstring (see extract_function_doc_info).

    Returns:
        The list of differences, in French (empty when the docstring matches the signature):
        undocumented parameters, documented parameters that do not exist, mandatory /
        optional mismatches, and a different order.
    """
    signature = {name: p.default is inspect.Parameter.empty
                 for name, p in inspect.signature(func).parameters.items()
                 if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
    issues = [f"paramètre non documenté : {name}" for name in signature if name not in params]
    issues += [f"paramètre documenté absent de la signature : {name}" for name in params if name not in signature]
    for name, mandatory in signature.items():
        if name in params and params[name]["required"] != mandatory:
            expected = "mandatory" if mandatory else "optional"
            issues.append(f"paramètre {name} : la signature le rend {expected}, la docstring dit le contraire")
    common_signature = [name for name in signature if name in params]
    common_doc = [name for name in params if name in signature]
    if common_signature != common_doc:
        issues.append(f"ordre différent de la signature : {', '.join(common_doc)} au lieu de "
                      f"{', '.join(common_signature)}")
    return issues


def extract_function_doc_info(funcs: dict) -> dict:
    """Extract structured documentation from the docstrings of the given functions.

    Args:
        funcs: Mapping of function name -> function object.

    Returns:
        {function_name: {
            "description": str,            text before "Parameters:"
            "params": {name: {"type", "required", "desc", "example"?, "choices"?, "keys"?}},
            "raw_params": {name: raw "- Input-..." line},
            "returns": str,                text of the Returns section ("" if absent)
            "output_type": str | None,     text after "Output type:"
            "signature_issues": [str],     differences with the real signature (check_signature)
        }}
        The "keys" of a dict parameter map each sub-key to {"type", "required", "desc", "choices"?}.
    """
    doc_info = {}
    for func_name, func in funcs.items():
        lines = (inspect.getdoc(func) or "").splitlines()
        description, parameter_lines, returns_lines = _split_sections(lines)
        params, raw_params = _parse_parameters(parameter_lines)
        returns, output_type = _parse_returns(returns_lines)
        doc_info[func_name] = {
            "description": "\n".join(line.strip() for line in description).strip(),
            "params": params,
            "raw_params": raw_params,
            "returns": returns,
            "output_type": output_type,
            "signature_issues": check_signature(func, params),
        }
    return doc_info


def discover_operations() -> dict[str, Callable]:
    """Return the operations of the project: documented functions of the operations and auth packages.

    A function is an operation when its docstring has a "Parameters:" section (the shared
    helpers use "Args:"). Importing the operation modules sends no request.

    Returns:
        {function name: function}, sorted by name.
    """
    import facebook_agent.auth
    import facebook_agent.operations

    found = {}
    for package in (facebook_agent.operations, facebook_agent.auth):
        for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            module = importlib.import_module(info.name)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                doc = inspect.getdoc(func) or ""
                if func.__module__ == module.__name__ and not name.startswith("_") \
                        and re.search(r"^Parameters\s*:\s*$", doc, re.M):
                    found[name] = func
    return dict(sorted(found.items()))


if __name__ == "__main__":
    # Vérification hors ligne : écarts entre docstrings et signatures de toutes les opérations
    report = extract_function_doc_info(discover_operations())
    problems = {name: entry["signature_issues"] for name, entry in report.items() if entry["signature_issues"]}
    print(f"{len(report)} opérations analysées, {len(problems)} avec des écarts.")
    for name, issues in problems.items():
        for issue in issues:
            print(f"  {name} : {issue}")

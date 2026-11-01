"""Protected Lead Ads forms (optional): forms that the code never archives nor uses in an ad.

The IDs come from PROTECTED_LEAD_FORM_IDS in the .env, empty by default: then no form is
protected. It is useful with forms that collect real leads. The agent's executor and the
interactive menu check them before archive_lead_form and create_ad; to use such a form, its ID
must first be removed from the .env.
"""

PROTECTED_OPERATIONS = {"archive_lead_form": "form_id", "create_ad": "lead_form_id"}
USABLE_FORM_STATUS = "ACTIVE"  # statut d'un formulaire Lead Ads qu'une publicité peut utiliser


def form_usage_problems(form: dict, form_id: str, page_id: str) -> list[str]:
    """Reasons why a Lead Ads form cannot be used in an ad of page_id (empty list = usable).

    Args:
        form: Fields of the form read with GET /{form_id}?fields=status,page.
        form_id: ID of the form.
        page_id: Page of the ad.

    Returns:
        The problems, in French: the form is not ACTIVE, or belongs to another page.
    """
    problems = []
    if form.get("status") != USABLE_FORM_STATUS:
        problems.append(f"le formulaire {form_id} n'est pas actif (statut {form.get('status')!r}) : "
                        "un formulaire archivé ne peut pas recevoir de leads.")
    owner = str((form.get("page") or {}).get("id", ""))
    if owner != str(page_id):
        problems.append(f"le formulaire {form_id} appartient à une autre page ({owner or 'inconnue'}), pas à {page_id}.")
    return problems


def protected_form_ids(raw: str | None) -> frozenset[str]:
    """IDs of the protected forms, from the comma-separated value of the .env.

    Args:
        raw: Value of PROTECTED_LEAD_FORM_IDS (e.g. "123, 456"), or None.

    Returns:
        The IDs, without spaces or empty items.
    """
    return frozenset(item.strip() for item in (raw or "").split(",") if item.strip())


def protected_form_problem(name: str, arguments: dict, protected: frozenset[str]) -> str | None:
    """Refusal reason when an operation targets a protected form, or None.

    Args:
        name: Name of the operation.
        arguments: Its arguments.
        protected: IDs of the protected forms.

    Returns:
        A sentence in French for archive_lead_form or create_ad on a protected form, else None.
    """
    param = PROTECTED_OPERATIONS.get(name)
    form_id = str(arguments.get(param) or "").strip() if param else ""
    if form_id and form_id in protected:
        return (f"formulaire protégé ({form_id}) : il n'est jamais archivé ni utilisé dans une publicité par le code. "
                "Pour l'utiliser, retire son ID de PROTECTED_LEAD_FORM_IDS dans le .env.")
    return None

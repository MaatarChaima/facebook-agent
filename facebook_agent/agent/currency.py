"""Currencies of the catalog: names and symbols -> ISO 4217 codes, checked before any confirmation.

"DT", "dinar", "dinars" -> "TND"; "€", "euro" -> "EUR"; "$", "dollar" -> "USD"... A value that is
neither a known alias nor an ISO 4217 code is refused with a clear message.
"""
import re

# Codes ISO 4217 en vigueur (liste de l'ISO, monnaies actives)
ISO_4217 = frozenset("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF
CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD
GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR
LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK
PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT
TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD XDR
XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG ZWL
""".split())

# Noms et symboles courants -> code ISO 4217 (comparés en minuscules, sans point final)
ALIASES = {
    "dt": "TND", "dinar": "TND", "dinars": "TND", "dinar tunisien": "TND", "dinars tunisiens": "TND", "د.ت": "TND",
    "€": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "us$": "USD", "dollar": "USD", "dollars": "USD", "dollar américain": "USD",
    "£": "GBP", "livre": "GBP", "livres": "GBP", "livre sterling": "GBP",
    "dh": "MAD", "dhs": "MAD", "dirham": "MAD", "dirhams": "MAD", "dirham marocain": "MAD",
    "da": "DZD", "dinar algérien": "DZD", "dinars algériens": "DZD",
    "chf": "CHF", "franc suisse": "CHF", "francs suisses": "CHF",
    "cfa": "XOF", "fcfa": "XOF", "franc cfa": "XOF", "francs cfa": "XOF",
    "¥": "JPY", "yen": "JPY", "yens": "JPY",
}
MENTION = re.compile(r"(?<![\w$€£¥])(" + "|".join(sorted((re.escape(a) for a in ALIASES), key=len, reverse=True))
                     + r"|[A-Z]{3})(?![\w])", re.IGNORECASE)


def normalize_currency(value: str | None) -> str | None:
    """ISO 4217 code of a currency written as a code, a name or a symbol.

    Args:
        value: Currency given by the user or the LLM ("DT", "dinars", "€", "eur", "TND"...).

    Returns:
        The code (e.g. "TND"), or None if the value is empty or not a known currency.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().rstrip(".").lower()
    if text in ALIASES:
        return ALIASES[text]
    code = text.upper()
    return code if code in ISO_4217 else None


def currencies_in_text(text: str) -> set[str]:
    """ISO 4217 codes of the currencies mentioned in a request ("35 DT", "en euros", "15 TND"...).

    Args:
        text: Request typed by the user.

    Returns:
        The set of codes.
    """
    found = set()
    for match in MENTION.finditer(text or ""):
        word = match.group(1)
        if word.isalpha() and word.isupper() is False and word.lower() not in ALIASES:
            continue  # « les », « une »… : trois lettres en minuscules, pas un code
        code = normalize_currency(word)
        if code:
            found.add(code)
    return found

"""Shared helpers for product prices (not an operation itself)."""
import re
from decimal import ROUND_HALF_UP, Decimal


def to_cents(price: str | float) -> int:
    """Convert a price to cents with exact decimal arithmetic (19.99 -> 1999).

    A comma is accepted as decimal separator (19,99 -> 1999). The Graph API expects
    catalog prices "with 2 digits added for cents", whatever the currency.

    Args:
        price: Price as a string or a number.

    Returns:
        The price in cents.

    Raises:
        decimal.InvalidOperation: The price is not a number.
    """
    amount = Decimal(str(price).strip().replace(",", "."))
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_display_price(text: str | float) -> Decimal:
    """Parse a price as displayed by the Graph API or typed by a user.

    Examples: "€21.50", "TND19.98", "19,98\\xa0€", "€1,299.00", "1 299,00 €", "9,99".
    The last separator is the decimal separator when 1 or 2 digits follow it;
    otherwise the separators are thousands separators.

    Args:
        text: Displayed price.

    Returns:
        The amount as a Decimal.

    Raises:
        ValueError: The text contains no number.
    """
    cleaned = re.sub(r"[^\d.,]", "", str(text))
    if not re.search(r"\d", cleaned):
        raise ValueError(f"prix illisible : {text!r}")
    last = max(cleaned.rfind("."), cleaned.rfind(","))
    decimals = len(cleaned) - last - 1 if last != -1 else 0
    if last != -1 and decimals in (1, 2):
        integer, fraction = cleaned[:last], cleaned[last + 1:]
    else:
        integer, fraction = cleaned, ""
    integer = re.sub(r"[.,]", "", integer) or "0"
    return Decimal(integer + ("." + fraction if fraction else ""))

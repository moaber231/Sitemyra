import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup


PRICE_PATTERN = re.compile(
    r"(?P<currency>[$€£])?\s*"
    r"(?P<amount>\d+(?:[.,]\d{1,2})?)"
)


CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}


def extract_price(
    html: str,
    selector: str,
    currency: str = "",
) -> tuple[Decimal, str, str]:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    element = soup.select_one(selector)

    if element is None:
        raise ValueError(
            f"Price selector did not match: {selector}"
        )

    raw_value = element.get_text(
        " ",
        strip=True,
    )

    match = PRICE_PATTERN.search(raw_value)

    if not match:
        raise ValueError(
            f"Could not parse price from: {raw_value}"
        )

    amount = match.group("amount")

    if "," in amount and "." not in amount:
        amount = amount.replace(",", ".")

    elif "," in amount and "." in amount:
        amount = amount.replace(",", "")

    try:
        price = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(
            f"Invalid price: {raw_value}"
        ) from exc

    detected_currency = (
        CURRENCY_MAP.get(match.group("currency"), "")
    )

    return (
        price,
        currency or detected_currency or "USD",
        raw_value,
    )

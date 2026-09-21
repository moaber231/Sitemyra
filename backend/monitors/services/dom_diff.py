import hashlib
import re

from bs4 import BeautifulSoup


IGNORED_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
)


def normalize_html(html: str, selector: str = "") -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(IGNORED_TAGS):
        tag.decompose()

    if selector:
        selected = soup.select_one(selector)

        if selected is None:
            raise ValueError(
                f"CSS selector did not match: {selector}"
            )

        soup = BeautifulSoup(
            str(selected),
            "html.parser",
        )

    text = soup.get_text(" ", strip=True)

    return re.sub(r"\s+", " ", text).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def content_changed(previous: str, current: str) -> bool:
    return content_hash(previous) != content_hash(current)

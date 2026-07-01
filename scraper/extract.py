import re
from datetime import datetime
from bs4 import BeautifulSoup


CURRENT_YEAR = datetime.now().year

FAMILY_KEYWORDS = [
    "family owned", "family-owned", "family business", "family run", "family-run",
    "founded by", "our founder", "second generation", "third generation",
    "multi-generation", "multigenerational", "father and son", "mother and daughter",
    "husband and wife", "brothers", "sisters", "since our family",
]

FOUNDER_TITLE_KEYWORDS = [
    "owner", "founder", "co-founder", "president", "ceo", "chief executive",
    "principal", "proprietor", "managing director", "general manager",
]

MODERN_FRAMEWORK_SIGNALS = [
    "__next", "_next/static", "nuxt", "gatsby", "vite", "react-dom",
    "vue.js", "angular.js", "svelte", "remix",
]

CATALOG_KEYWORDS = [
    "order online", "shop now", "add to cart", "place order", "online ordering",
    "product catalog", "browse products", "view catalog", "our products",
    "shop our", "buy now", "checkout",
]

PHONE_RE = re.compile(
    r"(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})"
)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
COPYRIGHT_YEAR_RE = re.compile(r"©\s*(\d{4})|copyright\s*©?\s*(\d{4})", re.IGNORECASE)
FOUNDING_YEAR_RE = re.compile(
    r"(?:since|established|founded|serving\s+\w+\s+since|est\.?)\s+((?:19|20)\d{2})"
    r"|(\d+)\s*(?:\+)?\s*years?\s+(?:in business|of (?:service|experience|operation))",
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r"\d{1,5}\s[\w\s.,-]{3,40},?\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?"
)
PERSON_NAME_RE = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})"
    r"[\s,\|·\-–]+(?:" + "|".join(FOUNDER_TITLE_KEYWORDS) + r")",
    re.IGNORECASE,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def detect_cms(homepage_html: str) -> str:
    lower = homepage_html.lower()
    if "wp-content" in lower or "wp-includes" in lower:
        return "WordPress"
    if 'name="generator" content="wordpress' in lower:
        return "WordPress"
    if "wix.com" in lower or "_wix_" in lower:
        return "Wix"
    if "squarespace" in lower:
        return "Squarespace"
    if "weebly" in lower:
        return "Weebly"
    if "shopify" in lower:
        return "Shopify"
    if "webflow" in lower:
        return "Webflow"
    if "drupal" in lower:
        return "Drupal"
    if "joomla" in lower:
        return "Joomla"
    return "Unknown"


def detect_modern_framework(homepage_html: str) -> bool:
    lower = homepage_html.lower()
    return any(sig in lower for sig in MODERN_FRAMEWORK_SIGNALS)


def has_viewport_meta(homepage_html: str) -> bool:
    soup = _soup(homepage_html)
    meta = soup.find("meta", attrs={"name": re.compile(r"viewport", re.I)})
    return meta is not None


def extract_copyright_year(all_text: str) -> int | None:
    matches = COPYRIGHT_YEAR_RE.findall(all_text)
    years = [int(y) for pair in matches for y in pair if y]
    return max(years) if years else None


def extract_founding_info(all_text: str) -> dict:
    """Returns {founding_year, years_in_business, snippet}."""
    match = FOUNDING_YEAR_RE.search(all_text)
    if not match:
        return {"founding_year": None, "years_in_business": None, "snippet": None}

    snippet_start = max(0, match.start() - 40)
    snippet_end = min(len(all_text), match.end() + 40)
    snippet = all_text[snippet_start:snippet_end].strip()
    snippet = re.sub(r"\s+", " ", snippet)

    explicit_year = match.group(1)
    years_ago = match.group(2)

    if explicit_year:
        founding_year = int(explicit_year)
        years_in_business = CURRENT_YEAR - founding_year
    elif years_ago:
        years_in_business = int(years_ago)
        founding_year = CURRENT_YEAR - years_in_business
    else:
        founding_year, years_in_business = None, None

    return {
        "founding_year": founding_year,
        "years_in_business": years_in_business,
        "snippet": snippet,
    }


def detect_family_language(all_text: str) -> tuple[bool, str | None]:
    lower = all_text.lower()
    for kw in FAMILY_KEYWORDS:
        idx = lower.find(kw)
        if idx != -1:
            start = max(0, idx - 30)
            end = min(len(all_text), idx + len(kw) + 60)
            snippet = all_text[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            return True, snippet
    return False, None


def extract_owner_contact(all_text: str) -> dict:
    owner_name = None
    owner_title = None

    match = PERSON_NAME_RE.search(all_text)
    if match:
        owner_name = match.group(1).strip()
        title_match = re.search(
            "|".join(FOUNDER_TITLE_KEYWORDS), match.group(0), re.IGNORECASE
        )
        owner_title = title_match.group(0).title() if title_match else None

    emails = EMAIL_RE.findall(all_text)
    generic_prefixes = {"info", "contact", "hello", "admin", "support", "sales", "office"}
    named_email = None
    generic_email = None
    for em in emails:
        local = em.split("@")[0].lower()
        if local in generic_prefixes:
            if not generic_email:
                generic_email = em
        else:
            if not named_email:
                named_email = em

    phones = PHONE_RE.findall(all_text)
    phone = phones[0] if phones else None

    address_match = ADDRESS_RE.search(all_text)
    mailing_address = address_match.group(0).strip() if address_match else None

    return {
        "owner_name": owner_name,
        "owner_title": owner_title,
        "contact_email": named_email,
        "generic_email": generic_email,
        "phone": phone,
        "mailing_address": mailing_address,
    }


def detect_catalog(all_text: str) -> bool:
    lower = all_text.lower()
    return any(kw in lower for kw in CATALOG_KEYWORDS)


def word_count(all_text: str) -> int:
    return len(all_text.split())


def extract_signals(fetch_result: dict) -> dict:
    """Run all signal extractors. Returns a flat signals dict."""
    homepage_html = fetch_result.get("homepage_html") or ""
    all_text = fetch_result.get("all_text") or ""

    founding = extract_founding_info(all_text)
    family_found, family_snippet = detect_family_language(all_text)
    contact = extract_owner_contact(all_text)
    copyright_year = extract_copyright_year(all_text)

    return {
        "ssl": fetch_result.get("ssl", False),
        "cms": detect_cms(homepage_html),
        "has_modern_framework": detect_modern_framework(homepage_html),
        "has_viewport_meta": has_viewport_meta(homepage_html) if homepage_html else False,
        "copyright_year": copyright_year,
        "copyright_stale": (
            (CURRENT_YEAR - copyright_year) >= 2 if copyright_year else False
        ),
        "founding_year": founding["founding_year"],
        "years_in_business": founding["years_in_business"],
        "founding_snippet": founding["snippet"],
        "founding_15_plus": (
            founding["years_in_business"] >= 15 if founding["years_in_business"] else False
        ),
        "family_language": family_found,
        "family_snippet": family_snippet,
        "has_catalog": detect_catalog(all_text),
        "word_count": word_count(all_text),
        **contact,
        "fetch_error": fetch_result.get("fetch_error"),
    }

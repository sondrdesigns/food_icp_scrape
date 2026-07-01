import time
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


NAV_PAGE_KEYWORDS = ["about", "contact", "team", "our-story", "our-team", "who-we-are", "history"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SondrLeadFinder/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_html_requests(url: str, timeout: int) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        if len(resp.text.strip()) < 200:
            return None
        return resp.text
    except Exception:
        return None


def _get_html_playwright(url: str, timeout: int) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            content = page.content()
            browser.close()
            return content
    except Exception:
        return None


def fetch_page(url: str, timeout: int = 15) -> str | None:
    html = _get_html_requests(url, timeout)
    if html is None:
        html = _get_html_playwright(url, timeout)
    return html


def _find_subpage_urls(homepage_html: str, base_url: str, max_pages: int) -> list[str]:
    soup = BeautifulSoup(homepage_html, "lxml")
    base = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    found = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip().lower()
        full = urljoin(base, href)
        path = urlparse(full).path.strip("/").lower()

        if urlparse(full).netloc != urlparse(base_url).netloc:
            continue
        if full in seen:
            continue
        if any(kw in path or kw in href for kw in NAV_PAGE_KEYWORDS):
            found.append(full)
            seen.add(full)
        if len(found) >= max_pages - 1:
            break

    return found


def fetch_site(
    url: str,
    timeout: int = 15,
    delay: float = 1.5,
    max_pages: int = 4,
) -> dict:
    """
    Fetch homepage + relevant subpages.
    Returns dict with keys: homepage_html, subpages (list of html strings),
    all_text (combined), ssl (bool), fetch_error (str|None).
    """
    # Normalise to https first, fall back to http
    parsed = urlparse(url)
    https_url = url if parsed.scheme == "https" else url.replace("http://", "https://", 1)

    ssl = True
    homepage_html = fetch_page(https_url, timeout)
    if homepage_html is None:
        ssl = False
        http_url = https_url.replace("https://", "http://", 1)
        homepage_html = fetch_page(http_url, timeout)

    if homepage_html is None:
        return {
            "homepage_html": None,
            "subpages": [],
            "all_text": "",
            "ssl": False,
            "fetch_error": "Could not fetch homepage via HTTPS or HTTP",
        }

    time.sleep(delay)

    subpage_urls = _find_subpage_urls(homepage_html, https_url if ssl else url, max_pages)
    subpages_html = []
    for sub_url in subpage_urls:
        html = fetch_page(sub_url, timeout)
        if html:
            subpages_html.append(html)
        time.sleep(delay)

    all_html_parts = [homepage_html] + subpages_html
    all_text = " ".join(
        BeautifulSoup(h, "lxml").get_text(separator=" ", strip=True)
        for h in all_html_parts
    )

    return {
        "homepage_html": homepage_html,
        "subpages": subpages_html,
        "all_text": all_text,
        "ssl": ssl,
        "fetch_error": None,
    }

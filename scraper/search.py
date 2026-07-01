import itertools
import time
import requests
import tldextract


SERPER_URL = "https://google.serper.dev/search"

QUERY_TEMPLATES = [
    '"{category}" {region} -site:zoominfo.com -site:linkedin.com -site:yelp.com -site:bbb.org',
    '"since 19" "{category}" {region}',
    'intitle:"{category}" inurl:about {region}',
]


def generate_queries(regions: list[str], category_terms: list[str]) -> list[dict]:
    """Cross regions × categories × templates into a flat list of query dicts."""
    queries = []
    for region, category in itertools.product(regions, category_terms):
        for template in QUERY_TEMPLATES:
            queries.append({
                "query": template.format(category=category, region=region),
                "region": region,
                "category": category,
            })
    return queries


def search(query: str, api_key: str, num: int = 10) -> list[str]:
    """Call Serper.dev and return a list of result URLs."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num}
    resp = requests.post(SERPER_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [r["link"] for r in data.get("organic", [])]


def collect_urls(
    regions: list[str],
    category_terms: list[str],
    api_key: str,
    exclude_domains: list[str],
    results_per_query: int = 10,
    delay: float = 1.0,
) -> list[dict]:
    """
    Run all generated queries, dedup by root domain, and filter excluded domains.
    Returns list of dicts: {url, region, category}.
    """
    queries = generate_queries(regions, category_terms)
    exclude_set = set(exclude_domains)
    seen_domains: set[str] = set()
    results: list[dict] = []

    for q in queries:
        try:
            urls = search(q["query"], api_key, num=results_per_query)
        except Exception as e:
            print(f"  [search error] {q['query']!r}: {e}")
            urls = []

        for url in urls:
            ext = tldextract.extract(url)
            root = f"{ext.domain}.{ext.suffix}".lower()

            if root in seen_domains:
                continue
            if any(excl in root for excl in exclude_set):
                continue

            seen_domains.add(root)
            results.append({
                "url": url,
                "root_domain": root,
                "region": q["region"],
                "category": q["category"],
            })

        time.sleep(delay)

    return results

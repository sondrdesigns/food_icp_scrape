HARD_EXCLUDE_REASONS = {
    "has_modern_framework": "Site uses a modern JS framework — likely not ICP",
    "is_national_brand": "Matches national distributor brand name",
    "is_dtc_ecommerce": "Has online catalog/checkout — DTC e-commerce, not ICP",
}


def _is_national_brand(company_name: str, url: str, national_keywords: list[str]) -> bool:
    text = (company_name + " " + url).lower()
    return any(kw.lower() in text for kw in national_keywords)


def score_lead(
    signals: dict,
    weights: dict,
    national_keywords: list[str],
    company_name: str = "",
    url: str = "",
) -> tuple[int, list[str]]:
    """
    Returns (score, flags).
    score = 0 means hard-excluded.
    flags = list of human-readable notes about scoring.
    """
    flags = []

    # Hard excludes
    if signals.get("has_modern_framework"):
        return 0, ["HARD EXCLUDE: " + HARD_EXCLUDE_REASONS["has_modern_framework"]]

    if _is_national_brand(company_name, url, national_keywords):
        return 0, ["HARD EXCLUDE: " + HARD_EXCLUDE_REASONS["is_national_brand"]]

    # Catalog presence on its own isn't a hard exclude — only combined with clear DTC signals
    # (we keep regional suppliers who have basic ordering portals)

    score = 0

    # Outdated CMS / no SSL / no mobile viewport (up to weight value)
    outdated_signals = []
    cms = signals.get("cms", "Unknown")
    if cms in ("WordPress", "Drupal", "Joomla") and not signals.get("has_modern_framework"):
        outdated_signals.append(f"CMS: {cms}")
    if not signals.get("ssl"):
        outdated_signals.append("No SSL")
    if not signals.get("has_viewport_meta"):
        outdated_signals.append("No mobile viewport")

    if outdated_signals:
        # Scale: all three = full weight; two = 2/3; one = 1/3
        portion = len(outdated_signals) / 3
        contrib = round(weights.get("outdated_cms_no_ssl_no_viewport", 30) * portion)
        score += contrib
        flags.append(f"+{contrib} outdated signals ({', '.join(outdated_signals)})")

    # Stale copyright
    if signals.get("copyright_stale"):
        yr = signals.get("copyright_year")
        contrib = weights.get("stale_copyright_year", 15)
        score += contrib
        flags.append(f"+{contrib} stale copyright (© {yr})")

    # Thin content / no catalog
    wc = signals.get("word_count", 0)
    has_catalog = signals.get("has_catalog", False)
    if wc < 400 or not has_catalog:
        contrib = weights.get("thin_content_no_catalog", 15)
        score += contrib
        reasons = []
        if wc < 400:
            reasons.append(f"thin content ({wc} words)")
        if not has_catalog:
            reasons.append("no online catalog")
        flags.append(f"+{contrib} {', '.join(reasons)}")

    # Founding 15+ years ago
    if signals.get("founding_15_plus"):
        contrib = weights.get("founding_year_15_plus", 15)
        score += contrib
        yib = signals.get("years_in_business")
        flags.append(f"+{contrib} in business {yib}+ years")

    # Family/founder language
    if signals.get("family_language"):
        contrib = weights.get("family_founder_language", 10)
        score += contrib
        flags.append(f"+{contrib} family/founder language detected")

    # Named owner/contact found
    if signals.get("owner_name") or signals.get("contact_email"):
        contrib = weights.get("named_owner_contact", 15)
        score += contrib
        who = signals.get("owner_name") or signals.get("contact_email")
        flags.append(f"+{contrib} named contact found ({who})")

    return min(score, 100), flags

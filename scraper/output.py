import csv
from datetime import datetime

LEADS_COLUMNS = [
    "fit_score",
    "company_name",
    "website",
    "region",
    "category",
    "owner_name",
    "owner_title",
    "contact_email",
    "generic_email",
    "phone",
    "mailing_address",
    "founding_year_detected",
    "years_in_business",
    "cms",
    "ssl",
    "personalization_note_1",
    "personalization_note_2",
    "flags",
]

REVIEW_COLUMNS = LEADS_COLUMNS + ["review_reason"]


def _build_row(lead: dict) -> dict:
    signals = lead.get("signals", {})
    score_flags = lead.get("score_flags", [])

    # Personalization notes: pull factual snippets from signals, not invented text
    notes = []
    if signals.get("founding_snippet"):
        notes.append(signals["founding_snippet"][:120])
    if signals.get("family_snippet") and len(notes) < 2:
        notes.append(signals["family_snippet"][:120])

    row = {
        "fit_score": lead.get("fit_score", 0),
        "company_name": lead.get("company_name", ""),
        "website": lead.get("url", ""),
        "region": lead.get("region", ""),
        "category": lead.get("category", ""),
        "owner_name": signals.get("owner_name") or "",
        "owner_title": signals.get("owner_title") or "",
        "contact_email": signals.get("contact_email") or "",
        "generic_email": signals.get("generic_email") or "",
        "phone": signals.get("phone") or "",
        "mailing_address": signals.get("mailing_address") or "",
        "founding_year_detected": signals.get("founding_year") or "",
        "years_in_business": signals.get("years_in_business") or "",
        "cms": signals.get("cms") or "",
        "ssl": "Yes" if signals.get("ssl") else "No",
        "personalization_note_1": notes[0] if len(notes) > 0 else "",
        "personalization_note_2": notes[1] if len(notes) > 1 else "",
        "flags": " | ".join(score_flags),
    }
    return row


def _needs_manual_review(lead: dict) -> tuple[bool, str]:
    signals = lead.get("signals", {})
    reasons = []

    if signals.get("fetch_error"):
        reasons.append(f"fetch error: {signals['fetch_error']}")
    if not signals.get("owner_name"):
        reasons.append("no owner name found — manual lookup needed")
    if lead.get("fit_score", 0) == 0 and not any(
        "HARD EXCLUDE" in f for f in lead.get("score_flags", [])
    ):
        reasons.append("zero score but not hard-excluded — ambiguous ICP fit")

    return bool(reasons), "; ".join(reasons)


def write_outputs(
    leads: list[dict],
    leads_path: str,
    review_path: str,
    max_leads: int = 30,
) -> tuple[int, int]:
    """Write leads.csv and review_queue.csv. Returns (leads_written, review_written)."""
    qualified = [l for l in leads if l.get("fit_score", 0) > 0]
    qualified.sort(key=lambda l: l["fit_score"], reverse=True)
    qualified = qualified[:max_leads]

    review_rows = []
    lead_rows = []

    for lead in qualified:
        needs_review, reason = _needs_manual_review(lead)
        row = _build_row(lead)
        if needs_review:
            review_row = dict(row)
            review_row["review_reason"] = reason
            review_rows.append(review_row)
        else:
            lead_rows.append(row)

    # Also send hard-excluded leads with a fetch error to review
    for lead in leads:
        if lead.get("fit_score", 0) == 0:
            signals = lead.get("signals", {})
            if signals.get("fetch_error"):
                row = _build_row(lead)
                row["review_reason"] = f"fetch error: {signals['fetch_error']}"
                review_rows.append(row)

    _write_csv(leads_path, lead_rows, LEADS_COLUMNS)
    _write_csv(review_path, review_rows, REVIEW_COLUMNS)

    return len(lead_rows), len(review_rows)


def _write_csv(path: str, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

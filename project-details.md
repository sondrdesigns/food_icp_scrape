# Sondr ICP Finder — Build Spec

## Objective
Build a script/tool that finds small, family-owned regional food distribution companies (the "LNC Food" ICP) by searching the web, then scores each candidate's website on how outdated/neglected it is — surfacing the best-fit leads for a personalized letter outreach campaign.

Output: a ranked spreadsheet of ~15-30 qualified leads per run, with enough info (company name, owner name if findable, contact info, website, ICP fit score, and 1-2 personalization notes) to write a handwritten letter without further manual research.

---

## 1. Target profile (ICP) — what we're searching for

- Food distributors / wholesalers, NAICS 424410, 424420, 424480, 424490 equivalent
- Regional/local, not national chains (Sysco, US Foods, etc. are explicit exclusions)
- Founded 15+ years ago (signals: "since 19XX" / "since 20XX, X+ years" language on site)
- Family-owned or founder-led language ("family owned," founder's name in About page, multi-generation mentions)
- Revenue/size proxy: small team (look for staff directory size, "our team" page length, or LinkedIn employee count if accessible)
- Often ethnic/specialty niche: Asian, Latin, Mediterranean, Halal, Indian, Caribbean, etc. food distribution — but general/broadline regional distributors qualify too
- Serves restaurants, independent grocers, and/or chain stores within a metro/regional radius (not e-commerce DTC)

## 2. Target geography (configurable list, start with)
Hawaii, Boise ID, Spokane WA, Salt Lake City UT, Denver CO, and similar Inland West / secondary metros. Should be an editable list/config, not hardcoded, so it can expand to new markets later.

## 3. Pipeline overview

```
1. Query generation  →  2. Search execution  →  3. Result dedup/filter
        ↓
4. Site fetch  →  5. Signal extraction  →  6. ICP scoring
        ↓
7. Owner/contact extraction  →  8. Output to spreadsheet  →  9. Manual review queue
```

### Step 1 — Query generation
Cross a list of **category terms** with a list of **regions** to generate search queries. Category term examples:
- "food distributor"
- "wholesale food distribution"
- "Asian food distributor"
- "Latin food distributor"
- "Halal food wholesale"
- "Mediterranean food distributor"
- "Indian grocery distributor"
- "restaurant food supplier"
- "produce distributor"

Combine with search operators to filter out directories/aggregators:
- `"{category term}" {region} -site:zoominfo.com -site:linkedin.com -site:yelp.com -site:bbb.org`
- `"since 19" "{category term}" {region}` (catches founder-story language)
- `intitle:"food distribution" inurl:about {region}`

Config should store category terms and regions as separate editable lists so the cross-product can grow without code changes.

### Step 2 — Search execution
Need a programmatic search source. Options (pick one, document tradeoffs):
- **Google Custom Search JSON API** — requires API key + Custom Search Engine ID, 100 free queries/day, paid beyond that
- **Bing Web Search API** (via Azure) — similar quota model
- **SerpAPI** or similar scraping-as-a-service — costs money but avoids API key setup friction and handles rendering/blocking
- Raw scraping of Google search results directly is fragile/ToS-risky — avoid unless wrapped by one of the above

Script should be written so the search backend is a swappable module (one function: `search(query) -> list[url]`), so we're not locked into one provider.

### Step 3 — Dedup and pre-filter
- Dedup by root domain across all query results
- Drop known non-ICP domains: large national distributor brands, directories (FoodCoDirectory, ZoomInfo, Bloomberg, Crunchbase, Yelp, BBB, Chamber of Commerce sites, Instagram/Facebook-only presences), restaurant supply equipment sellers (different vertical)
- Keep a maintainable exclude-list (config file, editable)

### Step 4 — Site fetch
- Fetch homepage + About/Contact/Team pages if discoverable from nav links
- Use a real user-agent, respect robots.txt, add delay between requests (politeness/rate limiting — this is a small batch tool, not a crawler, so 1-2 req/sec max is plenty)
- Handle both static HTML (requests + BeautifulSoup) and JS-rendered sites (fallback to Playwright/Selenium if initial fetch returns near-empty body) — note JS-rendering will be rare for this ICP since outdated sites are usually static WordPress, but build the fallback anyway

### Step 5 — Signal extraction (the "is this an outdated site" detector)
Extract/detect per site:
| Signal | How |
|---|---|
| CMS/platform | Look for WordPress meta generator tag, wp-content paths, Wix/Squarespace fingerprints in HTML |
| SSL | Check if site loads on https without redirect issues |
| Mobile responsiveness | Check for viewport meta tag presence |
| Footer copyright year | Regex for "© [YYYY]" in footer HTML, compare to current year |
| Content depth | Word count of homepage + about page (very thin = neglected) |
| Founding year language | Regex for "since 19XX" / "since 20XX" / "X years" patterns |
| Family/founder language | Keyword match: "family owned," "founded by," "our founder," generational language |
| Online catalog/ordering | Check for product catalog pages, "order online," portal/login links |
| Contact method | Phone number only vs. contact form vs. named email |
| Social proof | Presence/absence of reviews, testimonials, case studies |

### Step 6 — ICP fit scoring
Combine signals into a 0-100 score. Suggested weighting (tune later based on results):
- Outdated CMS / no SSL / no mobile viewport: +30 (this is the core "needs Sondr" signal)
- Stale copyright year (2+ years old): +15
- Thin content / no online catalog: +15
- Founding year 15+ years ago: +15
- Family/founder language present: +10
- Named owner/contact found (not just generic form): +15
- Hard exclude (score = 0) if: national chain, DTC e-commerce brand, site is already modern (recent framework, good UX) — these aren't ICP regardless of other signals

### Step 7 — Owner/contact extraction
- Parse About/Team/Contact pages for a person's name + title (Owner, Founder, President, CEO)
- Parse for a named email if available (not just info@/contact@) — flag if only generic contact found, since that means manual lookup is needed before a letter can be personalized
- Pull mailing address if listed (needed for the physical letter)
- Pull phone number

### Step 8 — Output
CSV/spreadsheet with columns:
`company_name, website, region, category, fit_score, owner_name, owner_title, contact_email, generic_email, phone, mailing_address, founding_year_detected, personalization_note_1, personalization_note_2, flags (e.g. "no owner name found — manual lookup needed")`

Sort descending by fit_score. Cap output at top 30 per run by default (configurable).

`personalization_note` fields should auto-populate from extracted signals where possible — e.g. "Site says 'serving the Treasure Valley since 1998'" — short factual snippets pulled straight from the site text, not generated/invented, so they can drop directly into the letter template.

### Step 9 — Manual review queue
Separate output tab/file for borderline cases: ambiguous ICP fit, no owner name found, or fetch failures — these need a human to glance at before being added to the letter batch, rather than being silently dropped or silently included.

---

## Non-functional requirements
- Should run as a simple CLI script (`python find_leads.py --region "Boise, ID" --limit 30`), not a service — this is a periodic batch tool run manually before each outreach round, not a live pipeline
- Config-driven (regions, category terms, exclude-list, scoring weights all in an editable config file, not hardcoded)
- No invented/hallucinated data — every field either comes from extracted site text or is explicitly left blank/flagged for manual fill
- Reasonable rate limiting/politeness to avoid hammering small business sites
- Should degrade gracefully — if owner name extraction fails, still output the company with a flag rather than dropping it

## Open questions for the build (flag back if ambiguous)
- Which search backend to use depends on whether there's a Google/Bing API key available — confirm before building, or default to a stub/swappable interface
- Whether to add LinkedIn lookup for owner names as a secondary enrichment step (would need separate handling given LinkedIn's scraping restrictions)

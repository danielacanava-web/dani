#!/usr/bin/env python3
"""
Extract view counts from social media posts and update Airtable.

Supports:
  - X / Twitter  (x.com, twitter.com)
  - LinkedIn     (linkedin.com)

Authentication is cookie-based: supply a JSON file (or env vars) that contain
the browser cookies from an already-logged-in session.

Usage:
    python extract_views.py                 # process all records
    python extract_views.py --limit 50      # process at most 50 records
    python extract_views.py --dry-run       # print without updating Airtable
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Optional

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Configuration (all from environment variables)
# ---------------------------------------------------------------------------
AIRTABLE_API_KEY    = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID    = "app4Vmo8HXg9n2lK7"
AIRTABLE_TABLE_ID   = "tblwVdqPpjw4tr0mw"

# Path to a JSON file containing browser cookies exported from an authenticated
# X / Twitter session (use a browser extension such as "Cookie-Editor").
X_COOKIES_FILE      = os.environ.get("X_COOKIES_FILE", "x_cookies.json")

# Path to a JSON file containing browser cookies for an authenticated LinkedIn session.
LINKEDIN_COOKIES_FILE = os.environ.get("LINKEDIN_COOKIES_FILE", "linkedin_cookies.json")

# Chromium headless-shell executable (pre-installed in many environments).
# Set PLAYWRIGHT_CHROMIUM_PATH to override.
_DEFAULT_CHROMIUM = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
CHROMIUM_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", _DEFAULT_CHROMIUM)

# Airtable field IDs --------------------------------------------------------
F_POST_TITLE     = "fldGmORUyBpbWB4aA"
F_POST_URL       = "fldJHFyZcSg1SEeS1"
F_MENTION_URL    = "fld9Mvnrm0l4IPWDa"
F_POST_VIEWS     = "fld09hAtMD048utuL"   # X / Twitter "Post views"
F_MENTION_VIEWS  = "fldZ8voKeAMw6cYNk"  # X "Views (where company is mentioned)"
F_LI_URL         = "fldhcKBZLRLoy7stV"
F_LI_VIEWS       = "fldUgHeELSYtdOAcQ"  # LinkedIn View Count
F_STATUS         = "fldKdqmwjtSUXG4Ru"


# ---------------------------------------------------------------------------
# Shorthand → integer conversion
# ---------------------------------------------------------------------------
def parse_views(raw: str) -> Optional[int]:
    """
    Convert a human-readable view string to a plain integer.

    Examples:
        "137.3K"  →  137300
        "1.7M"    →  1700000
        "3,700"   →  3700
        "42"      →  42
    """
    if not raw:
        return None
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    upper = cleaned.upper()
    try:
        if upper.endswith("B"):
            return int(float(upper[:-1]) * 1_000_000_000)
        if upper.endswith("M"):
            return int(float(upper[:-1]) * 1_000_000)
        if upper.endswith("K"):
            return int(float(upper[:-1]) * 1_000)
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def is_x_url(url: str) -> bool:
    return bool(url and re.search(r"(twitter\.com|x\.com)", url, re.I))


def is_linkedin_url(url: str) -> bool:
    return bool(url and "linkedin.com" in url.lower())


def extract_tweet_id(url: str) -> Optional[str]:
    m = re.search(r"(?:twitter\.com|x\.com)/(?:i/)?(?:\w+/)?status/(\d+)", url)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Airtable helpers
# ---------------------------------------------------------------------------
def _airtable_headers() -> dict:
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_records_needing_views(offset: Optional[str] = None, page_size: int = 100) -> dict:
    """
    Return records where Post URL is set but Post views is blank.
    We also fetch the LinkedIn URL/views fields to handle LI-only posts.
    """
    params = {
        "filterByFormula": f'AND(NOT({{{F_POST_URL}}} = ""), {{{F_POST_VIEWS}}} = "")',
        "fields[]": [
            F_POST_TITLE, F_POST_URL, F_MENTION_URL,
            F_POST_VIEWS, F_MENTION_VIEWS,
            F_LI_URL, F_LI_VIEWS,
            F_STATUS,
        ],
        "pageSize": page_size,
    }
    if offset:
        params["offset"] = offset

    resp = requests.get(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}",
        headers=_airtable_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_record(record_id: str, fields: dict, dry_run: bool = False):
    """Patch a single Airtable record."""
    if not fields:
        return
    if dry_run:
        print(f"    [DRY RUN] Would update {record_id} with {fields}")
        return
    resp = requests.patch(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}/{record_id}",
        headers=_airtable_headers(),
        json={"fields": fields},
        timeout=30,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Cookie loading
# ---------------------------------------------------------------------------
def load_cookies(path: str) -> list:
    """Load cookies from a JSON file (Cookie-Editor export format)."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    # Accept both list of dicts and {"cookies": [...]} wrapper
    if isinstance(data, dict):
        data = data.get("cookies", [])
    # Playwright expects keys: name, value, domain, path, expires, httpOnly, secure, sameSite
    cookies = []
    for c in data:
        entry = {
            "name":     c.get("name", ""),
            "value":    c.get("value", ""),
            "domain":   c.get("domain", ""),
            "path":     c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure":   c.get("secure", False),
        }
        if "expirationDate" in c:
            entry["expires"] = int(c["expirationDate"])
        if "sameSite" in c:
            # Playwright only accepts "Strict", "Lax", "None"
            ss = c["sameSite"].capitalize()
            if ss in ("Strict", "Lax", "None"):
                entry["sameSite"] = ss
        cookies.append(entry)
    return cookies


# ---------------------------------------------------------------------------
# Playwright scraping
# ---------------------------------------------------------------------------
# CSS / text patterns for X/Twitter view count
# The view count appears as "NNN Views" in the page's aria labels
_X_VIEW_SELECTORS = [
    # New X.com UI: analytics section under the tweet
    "a[href$='/analytics'] span",
    "div[data-testid='viewCount'] span",
    # fallback: any element whose text looks like "<number> Views"
]

# CSS patterns for LinkedIn view count
_LI_VIEW_SELECTORS = [
    "span.social-details-social-counts__reactions-count",
    "span[data-test-id='social-counts-reactions']",
    ".feed-shared-social-action-bar__action-count",
    # impressions text block
    "li.social-details-social-counts__item span",
]


def _scrape_x_views(page, url: str) -> Optional[int]:
    """Navigate to an X/Twitter post and return the view count."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        # Wait for main tweet content to load
        page.wait_for_selector("article[data-testid='tweet']", timeout=20_000)
    except PlaywrightTimeout:
        print(f"    Timeout loading X post: {url}")
        return None

    # Strategy 1: look for the analytics link that shows view count
    # e.g. "137.3K Views" visible as text near the tweet
    try:
        # The view count is usually in a group of metrics at the bottom of the tweet
        # It appears in a <span> inside an <a> whose href ends in "/analytics"
        view_el = page.query_selector("a[href$='/analytics']")
        if view_el:
            text = view_el.inner_text().strip()
            # text might be "137.3K\nViews" or "137.3K Views"
            nums = re.findall(r"[\d,\.]+[KkMmBb]?", text)
            if nums:
                count = parse_views(nums[0])
                if count is not None:
                    return count
    except Exception:
        pass

    # Strategy 2: scan all spans for "Views" pattern
    try:
        spans = page.query_selector_all("span")
        for span in spans:
            text = span.inner_text().strip()
            if re.search(r"views?", text, re.I) and len(text) < 40:
                nums = re.findall(r"[\d,\.]+[KkMmBb]?", text)
                if nums:
                    count = parse_views(nums[0])
                    if count is not None:
                        return count
    except Exception:
        pass

    # Strategy 3: look for aria-label containing "views"
    try:
        content = page.content()
        m = re.search(r'"viewCount"[^}]*"count"\s*:\s*"?([\d,\.]+[KkMmBb]?)"?', content)
        if m:
            return parse_views(m.group(1))
        # aria-label="137K views" pattern
        m = re.search(r'aria-label="([\d,\.]+[KkMmBb]?)\s*[Vv]iews?"', content)
        if m:
            return parse_views(m.group(1))
        # "views_count":137300 style in JSON blobs
        m = re.search(r'"views?[_\s]?count"[^:]*:\s*(\d+)', content, re.I)
        if m:
            return int(m.group(1))
    except Exception:
        pass

    return None


def _scrape_li_views(page, url: str) -> Optional[int]:
    """Navigate to a LinkedIn post and return the impression/view count."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)  # let dynamic content render
    except PlaywrightTimeout:
        print(f"    Timeout loading LinkedIn post: {url}")
        return None

    try:
        content = page.content()
        # "X impressions" or "X views" patterns
        m = re.search(r'([\d,\.]+[KkMmBb]?)\s*(?:impression|view)', content, re.I)
        if m:
            return parse_views(m.group(1))
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------
def process_all(dry_run: bool = False, limit: Optional[int] = None):
    if not AIRTABLE_API_KEY:
        sys.exit("ERROR: AIRTABLE_API_KEY environment variable is not set.")

    x_cookies = load_cookies(X_COOKIES_FILE)
    li_cookies = load_cookies(LINKEDIN_COOKIES_FILE)

    if not x_cookies:
        print(f"WARNING: No X/Twitter cookies found at '{X_COOKIES_FILE}'.")
        print("         X/Twitter view counts will be skipped.")
        print("         Export cookies from a logged-in X session and save as JSON.\n")
    if not li_cookies:
        print(f"WARNING: No LinkedIn cookies found at '{LINKEDIN_COOKIES_FILE}'.")
        print("         LinkedIn view counts will be skipped.\n")

    total_processed = 0
    total_updated = 0
    offset = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_PATH,
            args=["--no-sandbox", "--ignore-certificate-errors"],
        )

        # Create separate contexts for X and LinkedIn (different cookie sets)
        x_ctx = browser.new_context(ignore_https_errors=True)
        li_ctx = browser.new_context(ignore_https_errors=True)

        if x_cookies:
            x_ctx.add_cookies(x_cookies)
        if li_cookies:
            li_ctx.add_cookies(li_cookies)

        x_page = x_ctx.new_page()
        li_page = li_ctx.new_page()

        try:
            while True:
                data = fetch_records_needing_views(offset=offset)
                records = data.get("records", [])
                if not records:
                    break

                for record in records:
                    if limit is not None and total_processed >= limit:
                        break

                    rec_id = record["id"]
                    fields = record.get("fields", {})
                    title = (fields.get(F_POST_TITLE) or "")[:70]
                    post_url = fields.get(F_POST_URL) or ""
                    mention_url = fields.get(F_MENTION_URL) or ""

                    print(f"\n[{total_processed + 1}] {title}")
                    print(f"    Post URL: {post_url[:80]}")

                    updates = {}

                    # --- X / Twitter post ---
                    if is_x_url(post_url) and x_cookies:
                        views = _scrape_x_views(x_page, post_url)
                        if views is not None:
                            print(f"    Post views: {views:,}")
                            updates[F_POST_VIEWS] = views
                        else:
                            print("    Post views: not found")

                        # Handle the "mention" URL if different from main post
                        if mention_url and mention_url != post_url and is_x_url(mention_url):
                            print(f"    Mention URL: {mention_url[:80]}")
                            mviews = _scrape_x_views(x_page, mention_url)
                            if mviews is not None:
                                print(f"    Mention views: {mviews:,}")
                                updates[F_MENTION_VIEWS] = mviews
                            else:
                                print("    Mention views: not found")

                    # --- LinkedIn post ---
                    elif is_linkedin_url(post_url) and li_cookies:
                        views = _scrape_li_views(li_page, post_url)
                        if views is not None:
                            print(f"    LinkedIn views: {views:,}")
                            # Store in Post views (F_POST_VIEWS) so the filter
                            # no longer picks this record up; also update LI field.
                            updates[F_POST_VIEWS] = views
                            updates[F_LI_VIEWS] = views
                        else:
                            print("    LinkedIn views: not found")

                    else:
                        print("    Skipped (no matching cookies or unsupported platform)")

                    # Update Airtable
                    if updates:
                        update_record(rec_id, updates, dry_run=dry_run)
                        total_updated += 1

                    total_processed += 1
                    time.sleep(0.5)  # gentle rate-limiting

                if limit is not None and total_processed >= limit:
                    break

                offset = data.get("offset")
                if not offset:
                    break

        finally:
            browser.close()

    print(f"\n\nDone. Processed {total_processed} record(s), updated {total_updated}.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to Airtable")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of records to process")
    args = parser.parse_args()
    process_all(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()

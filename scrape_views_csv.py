#!/usr/bin/env python3
"""
Scrape view counts from X/Twitter URLs and output a CSV.
No Airtable connection needed.

Usage:
    python scrape_views_csv.py urls.txt          # file with one URL per line
    python scrape_views_csv.py urls.txt -o out.csv
    python scrape_views_csv.py urls.txt --cookies x_cookies.json

The cookies file is a Cookie-Editor JSON export from a logged-in X session.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

_DEFAULT_CHROMIUM = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"


def parse_views(raw: str) -> Optional[int]:
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


def load_cookies(path: str) -> list:
    if not path or not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("cookies", [])
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
            ss = c["sameSite"].capitalize()
            if ss in ("Strict", "Lax", "None"):
                entry["sameSite"] = ss
        cookies.append(entry)
    return cookies


def scrape_x_views(page, url: str) -> Optional[int]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector("article[data-testid='tweet']", timeout=20_000)
    except PlaywrightTimeout:
        print(f"  Timeout: {url}", file=sys.stderr)
        return None

    try:
        view_el = page.query_selector("a[href$='/analytics']")
        if view_el:
            text = view_el.inner_text().strip()
            nums = re.findall(r"[\d,\.]+[KkMmBb]?", text)
            if nums:
                count = parse_views(nums[0])
                if count is not None:
                    return count
    except Exception:
        pass

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

    try:
        content = page.content()
        m = re.search(r'"viewCount"[^}]*"count"\s*:\s*"?([\d,\.]+[KkMmBb]?)"?', content)
        if m:
            return parse_views(m.group(1))
        m = re.search(r'aria-label="([\d,\.]+[KkMmBb]?)\s*[Vv]iews?"', content)
        if m:
            return parse_views(m.group(1))
        m = re.search(r'"views?[_\s]?count"[^:]*:\s*(\d+)', content, re.I)
        if m:
            return int(m.group(1))
    except Exception:
        pass

    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls_file", help="Text file with one X/Twitter URL per line")
    parser.add_argument("-o", "--output", default="scraped_views.csv", help="Output CSV path (default: scraped_views.csv)")
    parser.add_argument("--cookies", default="x_cookies.json", help="Path to Cookie-Editor JSON export from X session")
    parser.add_argument("--chromium", default=None, help="Path to Chromium executable")
    args = parser.parse_args()

    with open(args.urls_file) as f:
        urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]

    if not urls:
        sys.exit("No URLs found in file.")

    cookies = load_cookies(args.cookies)
    if not cookies:
        print(f"WARNING: No cookies loaded from '{args.cookies}'. Views may not be visible without login.", file=sys.stderr)

    chromium_path = args.chromium or os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", _DEFAULT_CHROMIUM)

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=chromium_path,
            args=["--no-sandbox", "--ignore-certificate-errors"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        if cookies:
            ctx.add_cookies(cookies)
        page = ctx.new_page()

        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
            views = scrape_x_views(page, url)
            results.append((url, views if views is not None else ""))
            print(f"  -> {views}", file=sys.stderr)
            time.sleep(0.5)

        browser.close()

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["post_url", "post_views"])
        writer.writerows(results)

    print(f"\nDone. Results saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

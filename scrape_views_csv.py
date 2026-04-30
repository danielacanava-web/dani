#!/usr/bin/env python3
"""
Scrape views, likes, comments and reposts from X/Twitter URLs and output a CSV.
No Airtable connection needed.

Usage:
    python scrape_views_csv.py urls.txt
    python scrape_views_csv.py urls.txt -o out.csv
    python scrape_views_csv.py urls.txt --cookies x_cookies.json
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


def parse_count(raw: str) -> Optional[int]:
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


def scrape_tweet(page, url: str) -> dict:
    result = {"views": "", "likes": "", "comments": "", "reposts": ""}

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector("article[data-testid='tweet']", timeout=20_000)
    except PlaywrightTimeout:
        print(f"  Timeout: {url}", file=sys.stderr)
        return result

    # --- Views ---
    try:
        view_el = page.query_selector("a[href$='/analytics']")
        if view_el:
            text = view_el.inner_text().strip()
            nums = re.findall(r"[\d,\.]+[KkMmBb]?", text)
            if nums:
                v = parse_count(nums[0])
                if v is not None:
                    result["views"] = v
    except Exception:
        pass

    if not result["views"]:
        try:
            content = page.content()
            m = re.search(r'aria-label="([\d,\.]+[KkMmBb]?)\s*[Vv]iews?"', content)
            if m:
                result["views"] = parse_count(m.group(1)) or ""
            if not result["views"]:
                m = re.search(r'"views?[_\s]?count"[^:]*:\s*(\d+)', content, re.I)
                if m:
                    result["views"] = int(m.group(1))
        except Exception:
            pass

    # --- Likes, comments, reposts via aria-labels on action buttons ---
    try:
        # Reply/comment count
        reply_el = page.query_selector("[data-testid='reply']")
        if reply_el:
            label = reply_el.get_attribute("aria-label") or ""
            m = re.search(r"([\d,\.]+[KkMmBb]?)\s*repl", label, re.I)
            if m:
                result["comments"] = parse_count(m.group(1)) or ""
            else:
                span = reply_el.query_selector("span[data-testid='app-text-transition-container']")
                if span:
                    t = span.inner_text().strip()
                    v = parse_count(t)
                    if v is not None:
                        result["comments"] = v

        # Repost count
        repost_el = page.query_selector("[data-testid='retweet']")
        if repost_el:
            label = repost_el.get_attribute("aria-label") or ""
            m = re.search(r"([\d,\.]+[KkMmBb]?)\s*repost", label, re.I)
            if m:
                result["reposts"] = parse_count(m.group(1)) or ""
            else:
                span = repost_el.query_selector("span[data-testid='app-text-transition-container']")
                if span:
                    t = span.inner_text().strip()
                    v = parse_count(t)
                    if v is not None:
                        result["reposts"] = v

        # Like count
        like_el = page.query_selector("[data-testid='like']")
        if like_el:
            label = like_el.get_attribute("aria-label") or ""
            m = re.search(r"([\d,\.]+[KkMmBb]?)\s*like", label, re.I)
            if m:
                result["likes"] = parse_count(m.group(1)) or ""
            else:
                span = like_el.query_selector("span[data-testid='app-text-transition-container']")
                if span:
                    t = span.inner_text().strip()
                    v = parse_count(t)
                    if v is not None:
                        result["likes"] = v
    except Exception:
        pass

    # --- Fallback: scan aria-labels across the page ---
    try:
        if not result["comments"] or not result["reposts"] or not result["likes"]:
            content = page.content()
            if not result["comments"]:
                m = re.search(r'"reply_count"\s*:\s*(\d+)', content)
                if m:
                    result["comments"] = int(m.group(1))
            if not result["reposts"]:
                m = re.search(r'"retweet_count"\s*:\s*(\d+)', content)
                if m:
                    result["reposts"] = int(m.group(1))
            if not result["likes"]:
                m = re.search(r'"favorite_count"\s*:\s*(\d+)', content)
                if m:
                    result["likes"] = int(m.group(1))
    except Exception:
        pass

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls_file", help="Text file with one X/Twitter URL per line")
    parser.add_argument("-o", "--output", default="scraped_views.csv", help="Output CSV (default: scraped_views.csv)")
    parser.add_argument("--cookies", default="x_cookies.json", help="Cookie-Editor JSON from logged-in X session")
    parser.add_argument("--chromium", default=None, help="Path to Chromium executable")
    args = parser.parse_args()

    with open(args.urls_file) as f:
        urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]

    if not urls:
        sys.exit("No URLs found in file.")

    cookies = load_cookies(args.cookies)
    if not cookies:
        print(f"WARNING: No cookies loaded from '{args.cookies}'. Metrics may require login.", file=sys.stderr)

    chromium_path = args.chromium or os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", _DEFAULT_CHROMIUM)

    rows = []
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
            metrics = scrape_tweet(page, url)
            rows.append({
                "post_url":  url,
                "views":     metrics["views"],
                "likes":     metrics["likes"],
                "comments":  metrics["comments"],
                "reposts":   metrics["reposts"],
            })
            print(f"  views={metrics['views']}  likes={metrics['likes']}  comments={metrics['comments']}  reposts={metrics['reposts']}", file=sys.stderr)
            time.sleep(0.5)

        browser.close()

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["post_url", "views", "likes", "comments", "reposts"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

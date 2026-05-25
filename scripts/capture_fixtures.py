#!/usr/bin/env python3
"""
Capture real HTML samples from target sites for use in refreshing test fixtures.

This script requires the full scraping infrastructure (cloakbrowser, proxy env vars).
Without these, it exits cleanly with a message.

Tests do NOT depend on the output of this script -- it exists for periodic
re-syncing of hand-crafted fixtures against real site structure.

Usage:
  python scripts/capture_fixtures.py --all          Capture all fixture types
  python scripts/capture_fixtures.py --list          Show available fixture types
  python scripts/capture_fixtures.py --type most_wanted  Capture a specific type
  python scripts/capture_fixtures.py --verify        Parse captured HTML and report
"""

import argparse
import os
import sys
import textwrap
from pathlib import Path

# Ensure project root is on sys.path for `from src.xxx` imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"

FIXTURE_TYPES = {
    "most_wanted": {
        "url": "https://www.javlibrary.com/cn/vl_mostwanted.php",
        "description": "JavLibrary Most Wanted list page",
        "parser": "list",
    },
    "top_rated": {
        "url": "https://www.javlibrary.com/cn/vl_bestrated.php",
        "description": "JavLibrary Top Rated list page",
        "parser": "list",
    },
    "video_detail": {
        "url": "https://www.javlibrary.com/cn/?v=javli4q4v4",
        "description": "JavLibrary video detail page (example: ABC-001)",
        "parser": "detail",
    },
    "search_result": {
        "url": "https://clg55.top/search?word=QUJD&sort=rele",
        "description": "clg55.top search results page",
        "parser": "search",
    },
    "search_detail": {
        "url": "https://clg55.top/information/abc123def456",
        "description": "clg55.top magnet detail page",
        "parser": "search_detail",
    },
}


def capture_fixture(name, info, sanitize=False):
    """Fetch a single fixture and save to tests/fixtures/live_<name>.html."""
    from src.page_utils import load_with_cf_bypass
    from src.config import PROXY

    url = info["url"]
    print(f"\n{'='*60}")
    print(f"Capturing: {name} ({info['description']})")
    print(f"URL: {url}")
    print(f"{'='*60}")

    html = load_with_cf_bypass(url, proxy=PROXY, wait=15, timeout=60, headless=True)
    if html is None:
        print(f"  ERROR: Failed to load {url}")
        return None

    if sanitize:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "link", "style"]):
            tag.decompose()
        html = str(soup)

    output_path = FIXTURES_DIR / f"live_{name}.html"
    output_path.write_text(html, encoding="utf-8")
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"  Saved: {output_path} ({size_kb:.1f} KB)")
    return html


def verify_fixtures():
    """Parse all captured live fixtures and report what each parser extracts."""
    from src.scraper import parse_list_page, parse_detail_page, parse_search_page, parse_search_detail_page, is_javlibrary_page
    from src.page_utils import is_cloudflare_challenge

    print("\n" + "="*60)
    print("Verification Report")
    print("="*60)

    live_files = list(FIXTURES_DIR.glob("live_*.html"))
    if not live_files:
        print("No captured fixtures found. Run --all first.")
        return

    for path in sorted(live_files):
        name = path.stem.replace("live_", "")
        html = path.read_text(encoding="utf-8")
        print(f"\n--- {name} ({path.name}) ---")
        print(f"  Size: {len(html.encode('utf-8')) / 1024:.1f} KB")
        print(f"  is_javlibrary_page: {is_javlibrary_page(html)}")
        print(f"  is_cloudflare_challenge: {is_cloudflare_challenge(html)}")

        if name in ("most_wanted", "top_rated"):
            results = parse_list_page(html)
            print(f"  parse_list_page: {len(results)} videos")
            for r in results[:3]:
                print(f"    {r['code']}: score={r['score']}, actresses={r['actresses']}, date={r['date']}")
        elif name == "video_detail":
            detail = parse_detail_page(html)
            print(f"  parse_detail_page: score={detail.get('score')}, duration={detail.get('duration')}, "
                  f"maker={detail.get('maker')}, actresses={detail.get('actresses')}")
        elif name == "search_result":
            _, results = parse_search_page(html)
            print(f"  parse_search_page: {len(results)} results")
            for url, title, dc in results[:3]:
                print(f"    {title}: dl_count={dc}")
        elif name == "search_detail":
            info = parse_search_detail_page(html)
            if info:
                print(f"  parse_search_detail_page: title={info.get('title')}, size={info.get('size')}, "
                      f"magnet={'yes' if info.get('magnet') else 'no'}")
            else:
                print(f"  parse_search_detail_page: None (no magnet found)")


def cmd_list():
    """Print available fixture types."""
    print("\nAvailable fixture types:\n")
    for name, info in FIXTURE_TYPES.items():
        print(f"  {name:20s}  {info['description']}")
        print(f"  {'':20s}  {info['url']}")
        print()


def cmd_capture_all(args):
    """Capture all fixture types."""
    results = {}
    for name, info in FIXTURE_TYPES.items():
        html = capture_fixture(name, info, sanitize=args.sanitize)
        results[name] = html is not None
    print(f"\nResults: {sum(results.values())}/{len(results)} captured successfully")


def cmd_capture_one(args):
    """Capture a single fixture type."""
    if args.type not in FIXTURE_TYPES:
        print(f"Unknown type: {args.type}")
        print(f"Available: {', '.join(FIXTURE_TYPES.keys())}")
        sys.exit(1)
    info = FIXTURE_TYPES[args.type]
    capture_fixture(args.type, info, sanitize=args.sanitize)


def main():
    parser = argparse.ArgumentParser(
        description="Capture real HTML from target sites for test fixtures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          %(prog)s --all           Capture all fixture types
          %(prog)s --type most_wanted  Capture just the most_wanted page
          %(prog)s --verify        Parse captured pages and report what was extracted
          %(prog)s --list          Show available fixture types
          %(prog)s --all --sanitize   Capture and strip script/link/style tags
        """),
    )
    parser.add_argument("--all", action="store_true", help="Capture all fixture types")
    parser.add_argument("--type", metavar="NAME", help="Capture a specific fixture type")
    parser.add_argument("--list", action="store_true", help="List available fixture types")
    parser.add_argument("--verify", action="store_true", help="Parse captured HTML and report extracted data")
    parser.add_argument("--sanitize", action="store_true", help="Strip <script>, <link>, <style> tags from captured HTML")

    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.verify:
        verify_fixtures()
    elif args.type:
        cmd_capture_one(args)
    elif args.all:
        cmd_capture_all(args)
    else:
        parser.print_help()
        print("\nTip: Use --all to capture all fixture types, or --list to see what's available.")


if __name__ == "__main__":
    main()

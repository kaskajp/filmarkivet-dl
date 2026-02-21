#!/usr/bin/env python3
"""
Download all videos listed under Filmarkivet "reklamfilm" category pages
by running: svtplay-dl -S <video_url>

Features:
- Auto-pagination
- Deduping
- Resume via --seen-file
- Optional --dry-run and rate limiting

Usage examples:
  python3 download_filmarkivet_reklamfilm.py
  python3 download_filmarkivet_reklamfilm.py --dry-run
  python3 download_filmarkivet_reklamfilm.py --sleep 1.0
  python3 download_filmarkivet_reklamfilm.py --max-pages 5
"""

import argparse
import os
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_START_URL = "https://www.filmarkivet.se/category/reklamfilm/"


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.movie_links = set()
        self.next_link = None
        self._current_a_href = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attr = dict(attrs)
        href = attr.get("href")
        if not href:
            return

        abs_url = urljoin(self.base_url, href)
        self._current_a_href = abs_url

        if "/movies/" in urlparse(abs_url).path:
            self.movie_links.add(abs_url)

        rel = (attr.get("rel") or "")
        cls = (attr.get("class") or "")

        rel_str = " ".join(rel) if isinstance(rel, (list, tuple)) else str(rel)
        cls_str = " ".join(cls) if isinstance(cls, (list, tuple)) else str(cls)

        is_next = False
        if "next" in rel_str.lower():
            is_next = True
        if re.search(r"\bnext\b", cls_str.lower()):
            is_next = True

        if is_next:
            self.next_link = abs_url

    def handle_endtag(self, tag):
        if tag.lower() == "a":
            self._current_a_href = None

    def handle_data(self, data):
        if self._current_a_href is None:
            return
        text = data.strip().lower()
        if text in ("nästa", "next", "next »", "nästa »"):
            self.next_link = self._current_a_href


def fetch_html(url: str, referer: str = None, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def load_seen(path: str) -> set[str]:
    if not path or not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def append_seen(path: str, url: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def run_svtplay_dl(url: str, dry_run: bool, output_dir: str = None) -> int:
    cmd = ["svtplay-dl", "-S"]
    if output_dir:
        cmd += ["-o", output_dir]
    cmd.append(url)
    print(">>", " ".join(cmd))
    if dry_run:
        return 0
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("ERROR: svtplay-dl not found in PATH. Install it and try again.", file=sys.stderr)
        return 127


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-url", default=DEFAULT_START_URL)
    ap.add_argument("--sleep", type=float, default=0.5, help="Sleep between downloads (seconds)")
    ap.add_argument("--page-sleep", type=float, default=0.2, help="Sleep between page fetches (seconds)")
    ap.add_argument("--max-pages", type=int, default=0, help="0 = no limit")
    ap.add_argument("--seen-file", default="seen_urls.txt", help="File to persist processed video URLs")
    ap.add_argument("--output-dir", default="downloads", help="Directory to save downloaded videos in")
    ap.add_argument("--dry-run", action="store_true", help="Print commands but do not run svtplay-dl")
    args = ap.parse_args()

    if args.output_dir and not args.dry_run:
        os.makedirs(args.output_dir, exist_ok=True)

    seen = load_seen(args.seen_file)
    visited_pages = set()

    page_url = args.start_url
    prev_url = None
    page_count = 0
    total_found = 0
    total_attempted = 0

    while page_url:
        if page_url in visited_pages:
            print(f"Stopping: already visited page {page_url}")
            break
        visited_pages.add(page_url)

        page_count += 1
        if args.max_pages and page_count > args.max_pages:
            print(f"Stopping: reached --max-pages={args.max_pages}")
            break

        print(f"\n=== Page {page_count}: {page_url} ===")
        try:
            html = fetch_html(page_url, referer=prev_url)
        except Exception as e:
            print(f"ERROR fetching {page_url}: {e}", file=sys.stderr)
            break

        parser = LinkExtractor(page_url)
        parser.feed(html)

        movie_links = sorted(parser.movie_links)
        total_found += len(movie_links)
        print(f"Found {len(movie_links)} movie links on this page.")

        for video_url in movie_links:
            if video_url in seen:
                continue
            total_attempted += 1
            rc = run_svtplay_dl(video_url, args.dry_run, args.output_dir)
            append_seen(args.seen_file, video_url)
            seen.add(video_url)

            if rc != 0:
                print(f"WARNING: svtplay-dl returned {rc} for {video_url}", file=sys.stderr)

            if args.sleep > 0:
                time.sleep(args.sleep)

        next_url = parser.next_link

        # Fallback: if rel/class/text detection failed, try a regex for rel="next"
        if not next_url:
            for pattern in [
                r'rel=["\']next["\']\s+href=["\']([^"\']+)["\']',
                r'href=["\']([^"\']+)["\']\s+rel=["\']next["\']',
            ]:
                m = re.search(pattern, html, flags=re.I)
                if m:
                    next_url = urljoin(page_url, m.group(1))
                    break

        prev_url = page_url
        if next_url:
            if args.page_sleep > 0:
                time.sleep(args.page_sleep)
            page_url = next_url
        else:
            page_url = None

    print("\n=== Done ===")
    print(f"Pages visited: {page_count}")
    print(f"Movie links found (sum across pages, incl duplicates): {total_found}")
    print(f"New downloads attempted: {total_attempted}")
    print(f"Seen file: {args.seen_file}")


if __name__ == "__main__":
    main()
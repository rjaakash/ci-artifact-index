#!/usr/bin/env python3
"""
sync_reddit.py

APKMirror-based, fully automatic, historical-safe downloader
for Reddit.

Flow:
- Locate release via uploads pagination
- Select correct APKM bundle variant using strict priority
- Follow download redirects
- Download the final APKM locally

Variant priority (STRICT):
1. universal + 120-640dpi
2. arm64-v8a + 120-640dpi
3. universal + 480dpi
4. arm64-v8a + 480dpi

Behavior:
- Downloads a single APKM bundle
- Does NOT upload anything
- Does NOT delete anything
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# -------------------------------------------------
# Static endpoints and runtime configuration
# -------------------------------------------------

APKMIRROR_BASE = "https://www.apkmirror.com"
UPLOADS_BASE = f"{APKMIRROR_BASE}/uploads/?appcategory=reddit"

REDDIT_VERSION = os.environ.get("REDDIT_VERSION")

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

# Browser-like headers (fix for 403)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.apkmirror.com/",
    "Connection": "keep-alive",
}

MAX_PAGES = 25

session = requests.Session()
session.headers.update(HEADERS)

# -------------------------------------------------
# Validate required inputs
# -------------------------------------------------

if not REDDIT_VERSION:
    print("ERROR: REDDIT_VERSION missing")
    sys.exit(1)

version_slug = f"reddit-{REDDIT_VERSION.replace('.', '-')}-release"

print(f"[+] Target Reddit version: {REDDIT_VERSION}")
print(f"[+] Looking for slug: {version_slug}")

# -------------------------------------------------
# Locate release page via uploads pagination
# -------------------------------------------------

release_url = None

for page in range(1, MAX_PAGES + 1):
    page_url = (
        UPLOADS_BASE if page == 1
        else f"{APKMIRROR_BASE}/uploads/page/{page}/?appcategory=reddit"
    )

    r = session.get(page_url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.select("a[href]"):
        if version_slug in a["href"]:
            release_url = urljoin(APKMIRROR_BASE, a["href"])
            break

    if release_url:
        break

if not release_url:
    print(f"ERROR: Version {REDDIT_VERSION} not found")
    sys.exit(1)

print(f"[+] Found release page: {release_url}")

# -------------------------------------------------
# Select APKM variant using strict priority
# -------------------------------------------------

r = session.get(release_url, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

def find_variant(keywords):
    for row in soup.select("div.table-row"):
        text = row.get_text(" ", strip=True).lower()
        if all(k in text for k in keywords):
            a = row.find("a", href=True)
            if a:
                return urljoin(APKMIRROR_BASE, a["href"])
    return None

variant_url = (
    find_variant(["bundle", "universal", "120-640dpi"]) or
    find_variant(["bundle", "arm64-v8a", "120-640dpi"]) or
    find_variant(["bundle", "universal", "480dpi"]) or
    find_variant(["bundle", "arm64-v8a", "480dpi"])
)

if not variant_url:
    print("ERROR: No suitable Reddit APKM variant found")
    sys.exit(1)

print(f"[+] Selected variant: {variant_url}")

# -------------------------------------------------
# Resolve final APKM URL
# -------------------------------------------------

r = session.get(variant_url, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

download_btn = soup.select_one("a.downloadButton")
if not download_btn:
    print("ERROR: Download button missing")
    sys.exit(1)

download_page = urljoin(APKMIRROR_BASE, download_btn["href"])

r = session.get(download_page, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

final_link = soup.select_one("a[rel='nofollow']")
if not final_link:
    print("ERROR: Final redirect missing")
    sys.exit(1)

apkm_url = urljoin(APKMIRROR_BASE, final_link["href"])

# -------------------------------------------------
# Download APKM bundle
# -------------------------------------------------

apkm_name = f"Reddit-{REDDIT_VERSION}.apkm"
apkm_path = TMP_DIR / apkm_name

print(f"[+] Downloading {apkm_name}")

with session.get(apkm_url, stream=True, timeout=120) as r:
    r.raise_for_status()
    with open(apkm_path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

print("[✓] APKM downloaded successfully")

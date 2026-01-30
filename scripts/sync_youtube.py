#!/usr/bin/env python3
"""
sync_youtube.py

APKMirror-based downloader for YouTube APK.

Responsibility:
- Locate the exact YouTube version on APKMirror
- Select the UNIVERSAL nodpi APK
- Follow download redirects
- Download the APK locally

This script:
- DOES NOT create GitHub releases
- DOES NOT use tokens
- DOES NOT commit files
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# -------------------------------------------------
# Runtime configuration
# -------------------------------------------------

APKMIRROR_BASE = "https://www.apkmirror.com"
UPLOADS_BASE = f"{APKMIRROR_BASE}/uploads/?appcategory=youtube"

YOUTUBE_VERSION = os.environ.get("YOUTUBE_VERSION")

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "ci-artifact-index/1.0"
}

MAX_PAGES = 25

# -------------------------------------------------
# Validate input
# -------------------------------------------------

if not YOUTUBE_VERSION:
    print("ERROR: YOUTUBE_VERSION missing")
    sys.exit(1)

version_slug = f"youtube-{YOUTUBE_VERSION.replace('.', '-')}-release"

print(f"[+] Target YouTube version: {YOUTUBE_VERSION}")
print(f"[+] Looking for slug: {version_slug}")

# -------------------------------------------------
# Locate release page via uploads pagination
# -------------------------------------------------

release_url = None

for page in range(1, MAX_PAGES + 1):
    page_url = (
        UPLOADS_BASE if page == 1
        else f"{APKMIRROR_BASE}/uploads/page/{page}/?appcategory=youtube"
    )

    print(f"[+] Scanning uploads page {page}")

    r = requests.get(page_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.select("a[href]"):
        if version_slug in a["href"]:
            release_url = urljoin(APKMIRROR_BASE, a["href"])
            break

    if release_url:
        break

if not release_url:
    print(f"[!] Version {YOUTUBE_VERSION} not found")
    sys.exit(1)

print(f"[+] Found release page: {release_url}")

# -------------------------------------------------
# Select UNIVERSAL nodpi APK variant
# -------------------------------------------------

r = requests.get(release_url, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

variant_url = None

for row in soup.select("div.table-row"):
    text = row.get_text(" ", strip=True).lower()

    if (
        "apk" in text
        and "bundle" not in text
        and "nodpi" in text
        and "universal" in text
    ):
        a = row.find("a", href=True)
        if a:
            variant_url = urljoin(APKMIRROR_BASE, a["href"])
            break

if not variant_url:
    print("[!] Universal nodpi APK not found")
    sys.exit(1)

print(f"[+] Selected variant: {variant_url}")

# -------------------------------------------------
# Open download page
# -------------------------------------------------

r = requests.get(variant_url, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

download_btn = soup.select_one("a.downloadButton")

if not download_btn:
    print("[!] Download button missing")
    sys.exit(1)

download_page = urljoin(APKMIRROR_BASE, download_btn["href"])

# -------------------------------------------------
# Resolve final APK URL
# -------------------------------------------------

r = requests.get(download_page, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

final_link = soup.select_one("a[rel='nofollow']")

if not final_link:
    print("[!] Final redirect link not found")
    sys.exit(1)

apk_url = urljoin(APKMIRROR_BASE, final_link["href"])

# -------------------------------------------------
# Download APK
# -------------------------------------------------

apk_name = f"YouTube-{YOUTUBE_VERSION}.apk"
apk_path = TMP_DIR / apk_name

print(f"[+] Downloading {apk_name}")

with requests.get(apk_url, headers=HEADERS, stream=True, timeout=120) as r:
    r.raise_for_status()
    with open(apk_path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

print(f"[✓] APK downloaded: {apk_path}")

# -------------------------------------------------
# Output path for workflow consumption
# -------------------------------------------------

print(f"APK_PATH={apk_path}")

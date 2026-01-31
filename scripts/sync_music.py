#!/usr/bin/env python3
"""
sync_music.py

APKMirror-based, fully automatic, historical-safe downloader
for YouTube Music.

Variant priority:
1. arm64-v8a + nodpi
2. armeabi-v7a + nodpi (fallback)

Behavior:
- Downloads a single APK
- Upload handled by GitHub Actions (release)
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# -------------------------------------------------
# Configuration
# -------------------------------------------------

APKMIRROR_BASE = "https://www.apkmirror.com"
UPLOADS_BASE = f"{APKMIRROR_BASE}/uploads/?appcategory=youtube-music"

MUSIC_VERSION = os.environ.get("MUSIC_VERSION")

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "ci-artifact-index/1.0"
}

MAX_PAGES = 25

# -------------------------------------------------
# Validate input
# -------------------------------------------------

if not MUSIC_VERSION:
    print("ERROR: MUSIC_VERSION missing")
    sys.exit(1)

version_slug = f"youtube-music-{MUSIC_VERSION.replace('.', '-')}-release"

print(f"[+] Target Music version: {MUSIC_VERSION}")
print(f"[+] Looking for slug: {version_slug}")

# -------------------------------------------------
# Locate release page
# -------------------------------------------------

release_url = None

for page in range(1, MAX_PAGES + 1):
    page_url = (
        UPLOADS_BASE if page == 1
        else f"{APKMIRROR_BASE}/uploads/page/{page}/?appcategory=youtube-music"
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
    print(f"[!] Version {MUSIC_VERSION} not found")
    sys.exit(1)

print(f"[+] Found release page: {release_url}")

# -------------------------------------------------
# Select APK variant (priority-based)
# -------------------------------------------------

r = requests.get(release_url, headers=HEADERS, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

def find_variant(priority_keywords):
    for row in soup.select("div.table-row"):
        text = row.get_text(" ", strip=True).lower()
        if all(k in text for k in priority_keywords):
            a = row.find("a", href=True)
            if a:
                return urljoin(APKMIRROR_BASE, a["href"])
    return None

variant_url = (
    find_variant(["apk", "nodpi", "arm64-v8a"]) or
    find_variant(["apk", "nodpi", "armeabi-v7a"])
)

if not variant_url:
    print("[!] No suitable APK variant found")
    sys.exit(1)

print(f"[+] Selected APK variant: {variant_url}")

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
    print("[!] Final download link missing")
    sys.exit(1)

apk_url = urljoin(APKMIRROR_BASE, final_link["href"])
print("[+] Final APK URL resolved")

# -------------------------------------------------
# Download APK
# -------------------------------------------------

apk_name = f"Music-{MUSIC_VERSION}.apk"
apk_path = TMP_DIR / apk_name

print(f"[+] Downloading {apk_name}")

with requests.get(apk_url, headers=HEADERS, stream=True, timeout=120) as r:
    r.raise_for_status()
    with open(apk_path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)

print("[✓] APK downloaded successfully")

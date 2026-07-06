"""
Look up direct Box PDF URLs for individual well completion reports.

Uses CADWR's public Box shared folder (no API key required — the web page
embeds the shared token and folder IDs in its HTML).

Folder structure:
  WellCompletionReports/
    San Diego County/          ← county_folder_id
      {TOWNSHIP}{RANGE}/       ← e.g. 13S03W
        {T}{R}{S}_{WCR}.pdf    ← e.g. 13S0320_WCR2025-001849.pdf

The plss_folders mapping ({township+range: folder_id}) is built at download
time by download_data.py and stored in data/real/box_plss_folders.json.
"""

import json
import os
import re
import urllib.request

BOX_ROOT = "https://cadwr.app.box.com/v/WellCompletionReports"
_TIMEOUT = 8


def load_plss_folder_map(path: str) -> dict:
    """Load the pre-built PLSS → Box folder_id mapping from JSON."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("plss_folders", {})


def _fetch_box_page_items(folder_id) -> tuple[list, int]:
    """
    Fetch items from a Box shared folder page (HTML scrape, no auth needed).
    Returns (items_list, page_count).
    """
    url = f"{BOX_ROOT}/folder/{folder_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "water-report-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        html = r.read().decode()
    match = re.search(r"postStreamData\s*=\s*(\{.*?\});", html, re.S)
    if not match:
        return [], 0
    data = json.loads(match.group(1))
    sf = data.get("/app-api/enduserapp/shared-folder", {})
    return sf.get("items", []), int(sf.get("pageCount", 1))


def get_wcr_file_urls(plss_folder_map: dict, nearby_wells: list) -> dict:
    """
    For each nearby well that has Township/Range/WCRNumber, look up its
    direct Box file URL.

    Returns {wcr_number: box_file_url} for all matched wells.
    Silently skips wells where Township/Range are missing or Box is unreachable.
    """
    # Group WCR numbers by PLSS section key
    plss_to_wcrs: dict[str, list] = {}
    for w in nearby_wells:
        t = (w.get("Township") or "").strip()
        r = (w.get("Range") or "").strip()
        wcr = (w.get("WCRNumber") or "").strip()
        if t and r and wcr:
            key = f"{t}{r}"
            plss_to_wcrs.setdefault(key, []).append(wcr)

    result: dict[str, str] = {}
    for plss_key, wcr_list in plss_to_wcrs.items():
        folder_id = plss_folder_map.get(plss_key)
        if not folder_id:
            continue
        try:
            items, page_count = _fetch_box_page_items(folder_id)
            # Fetch additional pages if needed (Box shows 20 per page)
            if page_count > 1:
                for page in range(2, page_count + 1):
                    url = f"{BOX_ROOT}/folder/{folder_id}?page={page}"
                    req = urllib.request.Request(url, headers={"User-Agent": "water-report-mvp/1.0"})
                    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                        html = r.read().decode()
                    match = re.search(r"postStreamData\s*=\s*(\{.*?\});", html, re.S)
                    if match:
                        d = json.loads(match.group(1))
                        items += d.get("/app-api/enduserapp/shared-folder", {}).get("items", [])

            # Match items to WCR numbers by filename pattern
            for item in items:
                if item.get("type") != "file":
                    continue
                name = item.get("name", "")
                # Filename: e.g. 13S0320_WCR2025-001849.pdf
                m = re.search(r"(WCR\d{4}-\d+)", name)
                if m and m.group(1) in wcr_list:
                    result[m.group(1)] = f"{BOX_ROOT}/file/{item['id']}"
        except Exception:
            pass  # Box unavailable or folder missing — skip silently

    return result

#!/usr/bin/env python3
"""
Build script — télécharge les données ArcGIS (CIR / Bellingcat) et génère index.html autonome.
Utilisé par GitHub Actions (quotidien) et en local.
"""
import json, urllib.request, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

HERE     = Path(__file__).parent
TEMPLATE = HERE / "template.html"
OUT      = HERE / "index.html"

ARCGIS_BASE   = "https://services-eu1.arcgis.com/06WOSMGHsCnaFyMp/arcgis/rest/services/EoR_completed_entries/FeatureServer/0/query"
ARCGIS_FIELDS = "Primary_category,Secondary_category,Description,Town_or_City,Credit,Link,latitude,longitude,TIMESTAMP,country,province,Entry_Number,OBJECTID"
PAGE_SIZE     = 2000
HEADERS       = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Project-Bot/1.0)", "Accept": "application/json"}


def fetch():
    features, offset = [], 0
    while True:
        params = {
            "f": "json", "where": "1=1", "outFields": ARCGIS_FIELDS,
            "resultRecordCount": PAGE_SIZE, "resultOffset": offset,
            "returnGeometry": "true", "spatialRel": "esriSpatialRelIntersects"
        }
        url = ARCGIS_BASE + "?" + urlencode(params)
        print(f"  offset={offset}…")
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
        batch = data.get("features", [])
        features.extend(batch)
        print(f"    {len(batch)} features, total={len(features)}")
        if not data.get("exceededTransferLimit", False) or not batch:
            break
        offset += len(batch)
    print(f"Total: {len(features)} features")
    return features


def parse(features):
    rows, skipped = [], 0
    for i, f in enumerate(features):
        p   = f.get("attributes") or {}
        geo = f.get("geometry")   or {}
        lat = p.get("latitude")  if p.get("latitude")  is not None else geo.get("y")
        lon = p.get("longitude") if p.get("longitude") is not None else geo.get("x")
        try:
            lat, lon = float(lat), float(lon)
            if not (lat or lon): raise ValueError
        except Exception:
            skipped += 1
            continue
        ts   = p.get("TIMESTAMP")
        date = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""
        cats = [c for c in [p.get("Primary_category"), p.get("Secondary_category")] if c]
        rows.append({
            "id":          p.get("Entry_Number", "") or str(p.get("OBJECTID", i)),
            "date":        date,
            "url":         p.get("Link", ""),
            "status":      "",
            "credit":      p.get("Credit", ""),
            "description": p.get("Description", ""),
            "country":     p.get("country", ""),
            "province":    p.get("province", ""),
            "district":    "",
            "city":        p.get("Town_or_City", ""),
            "lat":         lat,
            "lon":         lon,
            "categories":  cats
        })
    print(f"{len(rows)} incidents valides, {skipped} ignorés")
    return rows


def build(rows):
    now     = datetime.now(timezone.utc).isoformat()
    data_js = (
        f"/* OSINT Project — {now} — {len(rows)} incidents */\n"
        f"window.OSINT_DATA={json.dumps(rows, ensure_ascii=False, separators=(',', ':'))};\n"
        f"window.OSINT_UPDATED='{now}';\n"
    )
    template = TEMPLATE.read_text(encoding="utf-8")
    MARKER   = '<script src="osint_data.js" onerror="window._noLocalData=true"></script>'
    if MARKER not in template:
        print("ERREUR : marqueur non trouvé dans template.html")
        sys.exit(1)
    html = template.replace(MARKER, f"<script>\n{data_js}\n</script>")
    OUT.write_text(html, encoding="utf-8")
    mb = len(html.encode()) / 1024 / 1024
    print(f"index.html : {mb:.1f} Mo, {len(rows)} incidents, {now}")


if __name__ == "__main__":
    print("Téléchargement données ArcGIS (CIR)…")
    features = fetch()
    rows     = parse(features)
    build(rows)
    print("Build terminé")

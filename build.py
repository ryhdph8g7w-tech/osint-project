#!/usr/bin/env python3
"""
Build script — télécharge les données fraîches et génère index.html autonome.
Utilisé par GitHub Actions (quotidien) et en local.
"""
import json, urllib.request, sys
from datetime import datetime, timezone
from pathlib import Path

HERE     = Path(__file__).parent
TEMPLATE = HERE / "template.html"
OUT      = HERE / "index.html"
URL      = "https://eyesonrussia.org/events.geojson"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Project-Bot/1.0)"}

def fetch():
    print(f"→ Téléchargement depuis {URL}…")
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    features = data.get("features", [])
    print(f"  {len(features)} features reçues")
    return features

def parse(features):
    rows, skipped = [], 0
    for f in features:
        p  = f.get("properties") or {}
        co = (f.get("geometry") or {}).get("coordinates") or []
        try:
            lon, lat = float(co[0]), float(co[1])
            if not lat or not lon: raise ValueError
        except:
            skipped += 1; continue
        d   = (p.get("verifiedDate") or "")[:10]
        cats = p.get("categories") or []
        if isinstance(cats, str): cats = [cats]
        rows.append({"id": p.get("id",""), "date": d,
                     "url": p.get("url",""), "status": p.get("status",""),
                     "credit": p.get("credit",""), "description": p.get("description",""),
                     "country": p.get("country",""), "province": p.get("province",""),
                     "district": p.get("district",""), "city": p.get("city",""),
                     "lat": lat, "lon": lon, "categories": cats})
    print(f"  {len(rows)} incidents valides, {skipped} ignorés")
    return rows

def build(rows):
    now = datetime.now(timezone.utc).isoformat()
    data_js = (f"/* OSINT Project — {now} — {len(rows)} incidents */\n"
               f"window.OSINT_DATA={json.dumps(rows, ensure_ascii=False, separators=(',',':'))};\n"
               f"window.OSINT_UPDATED='{now}';\n")
    template = TEMPLATE.read_text(encoding="utf-8")
    MARKER   = '<script src="osint_data.js" onerror="window._noLocalData=true"></script>'
    if MARKER not in template:
        print("ERREUR : marqueur non trouvé dans template.html"); sys.exit(1)
    html = template.replace(MARKER, f"<script>\n{data_js}\n</script>")
    OUT.write_text(html, encoding="utf-8")
    mb = len(html.encode()) / 1024 / 1024
    print(f"→ index.html généré : {mb:.1f} Mo, {len(rows)} incidents, {now}")

if __name__ == "__main__":
    features = fetch()
    rows     = parse(features)
    build(rows)
    print("✓ Build terminé")

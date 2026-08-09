"""Fetch OSM building footprints around the 7 per-station-design stations.

The 3D bird's-eye views need real footprints. Amap's 3D buildings are drawn by
its JS API and are not obtainable here: the key available to this project is a
Web-service key, and the JS API rejects it with USERKEY_PLAT_NOMATCH (10009).
Amap also publishes no street-view API. So the volumes come from OSM, which is
the same basis as the rest of the base map and is redistributable under ODbL.

Height is the weak part and is kept visible rather than smoothed over: around
学知园 only 6 of 190 buildings carry `height` or `building:levels`. This script
records the tag as found and never fills one in; make_3d.py does the estimating
and marks estimated volumes differently from tagged ones.

Run: .venv/bin/python tools/fetch_buildings.py
Writes tools/data/osm_buildings.json. Skips the fetch if that file exists.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "osm_buildings.json")

RADIUS_M = 1200          # covers the largest measured 15-minute reach with margin
KEEP_TAGS = ("building", "building:levels", "building:part", "height",
             "min_height", "name", "amenity", "office", "shop")

# The main endpoint returns dispatcher runtime errors often enough that a single
# host is not a reliable build step; mirrors are tried in order.
ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def design_stations():
    data = json.load(open(os.path.join(DATA, "stations.geojson")))
    out = []
    for f in data["features"]:
        p = f["properties"]
        if p.get("scope_level") != "overall_design_area":
            continue
        lon, lat = f["geometry"]["coordinates"]
        out.append((p["name_zh"], lon, lat))
    return out


def query(lat, lon):
    return ('[out:json][timeout:90];(way["building"](around:%d,%.5f,%.5f);'
            'way["building:part"](around:%d,%.5f,%.5f););out geom tags;'
            % (RADIUS_M, lat, lon, RADIUS_M, lat, lon))


def fetch(q):
    # A healthy mirror answers one station in a few seconds, so the timeout is
    # short on purpose: a longer one buys nothing and a stalled socket then
    # blocks the whole run. An earlier version at 180s hung for 13 minutes on a
    # single station that a retry served in 3 seconds.
    body = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(4):
        for host in ENDPOINTS:
            try:
                req = urllib.request.Request(
                    host, data=body,
                    headers={"User-Agent": "haidian-tod-study/1.0"})
                with urllib.request.urlopen(req, timeout=45) as r:
                    return json.load(r)["elements"]
            except Exception as e:
                print("   %s attempt %d: %s" % (host.split("/")[2], attempt + 1,
                                                type(e).__name__), flush=True)
        time.sleep(8 * (attempt + 1))
    return None


def main():
    if os.path.exists(OUT):
        print("skip: %s exists" % OUT)
        return
    ways, tagged = {}, 0
    for name, lon, lat in design_stations():
        print("==", name, flush=True)
        els = fetch(query(lat, lon))
        if els is None:
            sys.exit("all Overpass endpoints failed for %s; rerun later" % name)
        n_new = 0
        for e in els:
            geo = e.get("geometry") or []
            pts = [[p["lon"], p["lat"]] for p in geo if p.get("lon") is not None]
            if len(pts) < 4:
                continue
            wid = str(e["id"])
            if wid in ways:
                continue
            t = e.get("tags", {})
            ways[wid] = {
                "pts": [[round(x, 6), round(y, 6)] for x, y in pts],
                "tags": {k: t[k] for k in KEEP_TAGS if k in t},
            }
            n_new += 1
            if "height" in t or "building:levels" in t:
                tagged += 1
        print("   %d ways, %d new" % (len(els), n_new), flush=True)
        time.sleep(2)

    doc = {
        "_source": "OpenStreetMap via Overpass, ODbL 1.0, "
                   "(c) OpenStreetMap contributors",
        "_radius_m": RADIUS_M,
        "_n_buildings": len(ways),
        "_n_with_height_tag": tagged,
        "_note": ("Footprints around the 7 per-station-design stations. Height "
                  "tags are recorded as found and never invented here: only %d "
                  "of %d buildings carry height or building:levels, so make_3d.py "
                  "estimates the rest from building type and renders estimated "
                  "volumes differently from tagged ones."
                  % (tagged, len(ways))),
        "buildings": ways,
    }
    json.dump(doc, open(OUT, "w"), ensure_ascii=False)
    print("\nwrote %s  %d buildings, %d with a height tag (%.1f%%)"
          % (OUT, len(ways), tagged, 100.0 * tagged / max(1, len(ways))))


if __name__ == "__main__":
    main()

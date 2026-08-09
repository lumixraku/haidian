"""Measure reachable walking extent per station as a polygon, not a circle.

For each of the 7 overall-design-area stations, 16 bearings at 22.5 degrees.
Along each bearing, probe several straight-line distances and record the actual
Amap walking route length. Then for each walking budget (minutes * 75 m),
interpolate the straight-line distance at which the route length hits the
budget. Those 16 distances are the polygon vertices.

This replaces radius = minutes * 75 / 1.35. That constant was wrong two ways:
the measured median detour is 1.75, and it is not constant across bearings — at
学知园 the 5-minute reach is 284m in the clear direction and 38m across 京藏高速.

Failures are counted and reported per station, never silently turned into a
zero-length vertex: an earlier threaded version at 8 workers lost 3-12 of 17
bearings to transient errors and printed medians of 0m, which looked like a
finding rather than a bug. Hence 3 workers and 6 retries with backoff.

Run: AMAP_KEY=... .venv/bin/python tools/fetch_walk.py
Writes tools/data/walk_isochrones.json. The key comes from the environment and
is never written into a file inside the repository.
"""
import datetime
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(DATA, "walk_isochrones.json")

KEY = os.environ.get("AMAP_KEY", "").strip()
if not KEY:
    sys.exit("AMAP_KEY not set")

R = 6371000.0
SPEED_MPM = 75
N_BEARINGS = 16
BEARINGS = [i * 360.0 / N_BEARINGS for i in range(N_BEARINGS)]
PROBES = [150, 300, 450, 600, 800, 1000, 1250]
MINUTES = [5, 10, 15]
FORMER_DETOUR = 1.35   # recorded only to show what each ring used to be

fail_count = 0


def design_stations():
    """The 7 per-station-design stations, from the same file the drawings use."""
    data = json.load(open(os.path.join(DATA, "stations.geojson")))
    out = []
    for f in data["features"]:
        p = f["properties"]
        if p.get("scope_level") != "overall_design_area":
            continue
        lon, lat = f["geometry"]["coordinates"]
        out.append((p["name_zh"], lon, lat))
    return out


def offset(lon, lat, bearing_deg, dist_m):
    br = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    dr = dist_m / R
    p2 = math.asin(math.sin(p1) * math.cos(dr)
                   + math.cos(p1) * math.sin(dr) * math.cos(br))
    l2 = l1 + math.atan2(math.sin(br) * math.sin(dr) * math.cos(p1),
                         math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(l2), math.degrees(p2)


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def walk(o_lon, o_lat, d_lon, d_lat):
    """Route length in metres, or None after exhausting retries."""
    global fail_count
    q = urllib.parse.urlencode({
        "key": KEY,
        "origin": "%.6f,%.6f" % (o_lon, o_lat),
        "destination": "%.6f,%.6f" % (d_lon, d_lat),
    })
    url = "https://restapi.amap.com/v3/direction/walking?" + q
    last = ""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.load(r)
            if d.get("status") == "1":
                paths = d.get("route", {}).get("paths") or []
                if paths:
                    return int(paths[0]["distance"])
                last = "no paths"
            else:
                last = "%s/%s" % (d.get("info"), d.get("infocode"))
        except Exception as e:
            last = type(e).__name__
        time.sleep(0.8 * (attempt + 1))
    fail_count += 1
    print("      probe failed after retries: %s" % last, file=sys.stderr, flush=True)
    return None


def probe_bearing(args):
    lon, lat, b = args
    out = []
    for dist in PROBES:
        dlon, dlat = offset(lon, lat, b, dist)
        route = walk(lon, lat, dlon, dlat)
        if route is None:
            continue
        out.append((haversine(lon, lat, dlon, dlat), route))
        time.sleep(0.15)
    return b, sorted(out)


def solve(pts, budget):
    """Straight-line distance whose route length equals budget, or None."""
    if len(pts) < 2:
        return None
    for (s0, r0), (s1, r1) in zip(pts, pts[1:]):
        if r0 <= budget <= r1 and r1 != r0:
            return s0 + (s1 - s0) * (budget - r0) / (r1 - r0)
    if budget < pts[0][1]:
        return pts[0][0] * budget / pts[0][1]
    return pts[-1][0] * budget / pts[-1][1]


def main():
    stations = {}
    incomplete_stations = []
    for name, lon, lat in design_stations():
        print("==", name, flush=True)
        with ThreadPoolExecutor(max_workers=3) as ex:
            got = list(ex.map(probe_bearing, [(lon, lat, b) for b in BEARINGS]))
        per_bearing = dict(got)
        short = [b for b, p in per_bearing.items() if len(p) < len(PROBES)]
        if short:
            print("   incomplete bearings: %d of %d" % (len(short), N_BEARINGS),
                  flush=True)
            incomplete_stations.append(name)
        entry = {"lon": lon, "lat": lat, "rings": {}}
        for mins in MINUTES:
            budget = mins * SPEED_MPM
            verts = []
            for b in BEARINGS:
                d = solve(per_bearing.get(b, []), budget)
                if d is not None:
                    verts.append([round(b, 1), round(d, 1)])
            if len(verts) < N_BEARINGS:
                print("   WARNING %2dmin: only %d/%d vertices"
                      % (mins, len(verts), N_BEARINGS), flush=True)
            rs = sorted(v[1] for v in verts)
            n = len(rs)
            med = rs[n // 2] if n % 2 else (rs[n // 2 - 1] + rs[n // 2]) / 2
            former = round(mins * SPEED_MPM / FORMER_DETOUR)
            entry["rings"][str(mins)] = {
                "vertices": verts, "median_m": round(med, 1),
                "min_m": rs[0], "max_m": rs[-1], "former_circle_m": former,
            }
            print("   %2dmin  median %4.0fm  min %3.0f  max %4.0f  (circle was %3dm, %+d%%)"
                  % (mins, med, rs[0], rs[-1], former,
                     round(100 * (med - former) / former)), flush=True)
        stations[name] = entry

    doc = {
        "_note": ("Measured walking isochrones from Amap direction/walking. Per "
                  "station, 16 bearings at 22.5 degrees; along each bearing several "
                  "straight-line probe distances were routed and the straight-line "
                  "distance at which the route length reaches the walking budget "
                  "(minutes * %d m/min) was interpolated. reach_m are those "
                  "distances, in metres, from the station point. Replaces the "
                  "earlier radius = minutes * %d / %s circle."
                  % (SPEED_MPM, SPEED_MPM, FORMER_DETOUR)),
        # The date is part of the evidence: a road opening or closure changes the
        # network, so a ring is only as current as the day it was measured.
        "_source": ("AutoNavi/Amap Web Service API v3 direction/walking, measured %s"
                    % datetime.date.today().isoformat()),
        "_speed_mpm": SPEED_MPM,
        "_n_bearings": N_BEARINGS,
        "_probe_distances_m": PROBES,
        "_failed_probes": fail_count,
        "stations": stations,
    }
    json.dump(doc, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("\nwrote %s   failed probes: %d" % (OUT, fail_count))
    if incomplete_stations:
        print("stations with incomplete bearings: %s"
              % ", ".join(incomplete_stations))
        print("rerun before using: a partial station under-reports its reach")


if __name__ == "__main__":
    main()

"""Shared base-map loading and projection for the Haidian rail-TOD drawings.

All geometry is projected to EPSG:32650 (UTM 50N) so distances and walk-time
rings are metric, not degrees.
"""
import json
import os

from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
from shapely.ops import transform as shp_transform

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
# Repo-relative, not an absolute home path: these scripts live in tools/ inside
# the repository, so a clone must resolve the brief geometry without editing.
REPO = os.path.dirname(HERE)
BOUNDARIES = os.path.join(REPO, "brief/site-package/geometry/provisional_boundaries.geojson")

_T = Transformer.from_crs("EPSG:4326", "EPSG:32650", always_xy=True)
_INV = Transformer.from_crs("EPSG:32650", "EPSG:4326", always_xy=True)


def prj(geom):
    return shp_transform(lambda x, y, z=None: _T.transform(x, y), geom)


def to_xy(lon, lat):
    return _T.transform(lon, lat)


KEY_LABELS = {
    "PROV-KEY-001": "众智园AI自主创新加速区",
    "PROV-KEY-002": "北京AI原点社区",
    "PROV-KEY-003": "大钟寺AI产业聚集区",
}

# Road weight by OSM class: motorway/trunk read as expressway barriers,
# which is the point of the walkability diagnosis.
ROAD_STYLE = {
    "motorway": dict(lw=2.4, color="#8a8f98", z=3),
    "trunk": dict(lw=2.0, color="#9aa0a8", z=3),
    "primary": dict(lw=1.4, color="#b3b8bf", z=2),
    "secondary": dict(lw=0.8, color="#c8ccd1", z=2),
    "tertiary": dict(lw=0.4, color="#d9dce0", z=1),
}
BARRIER_CLASSES = ("motorway", "trunk")


def _ways(path):
    if not os.path.exists(path):
        return []
    return json.load(open(path))["elements"]


def _way_line(e):
    geo = e.get("geometry") or []
    pts = [(p["lon"], p["lat"]) for p in geo if p.get("lon") is not None]
    if len(pts) < 2:
        return None
    return prj(LineString(pts))


def load_boundaries():
    feats = json.load(open(BOUNDARIES))["features"]
    return {f["properties"]["id"]: prj(shape(f["geometry"])) for f in feats}


def load_roads():
    out = {k: [] for k in ROAD_STYLE}
    for e in _ways(os.path.join(DATA, "osm_roads.json")):
        cls = e.get("tags", {}).get("highway")
        if cls not in out:
            continue
        ln = _way_line(e)
        if ln is not None:
            out[cls].append(ln)
    return out


def load_rail():
    heavy, metro = [], []
    for e in _ways(os.path.join(DATA, "osm_rail.json")):
        tags = e.get("tags", {})
        ln = _way_line(e)
        if ln is None:
            continue
        (heavy if tags.get("railway") == "rail" else metro).append(ln)
    return heavy, metro


def load_polys(kind):
    out = []
    for e in _ways(os.path.join(DATA, "osm_%s.json" % kind)):
        geo = e.get("geometry") or []
        pts = [(p["lon"], p["lat"]) for p in geo if p.get("lon") is not None]
        if len(pts) < 4:
            continue
        try:
            g = prj(shape({"type": "Polygon", "coordinates": [pts + [pts[0]]]}))
            if g.is_valid and g.area > 2000:
                out.append(g)
        except Exception:
            continue
    return out


def load_water_lines():
    out = []
    for e in _ways(os.path.join(DATA, "osm_water.json")):
        if e.get("tags", {}).get("waterway") != "river":
            continue
        ln = _way_line(e)
        if ln is not None:
            out.append(ln)
    return out


def load_stations():
    """21 stations with real coordinates, scope level and line refs."""
    data = json.load(open(os.path.join(DATA, "stations.geojson")))
    out = []
    for f in data["features"]:
        p = dict(f["properties"])
        lon, lat = f["geometry"]["coordinates"]
        p["lon"], p["lat"] = lon, lat
        p["x"], p["y"] = to_xy(lon, lat)
        p["pt"] = Point(p["x"], p["y"])
        out.append(p)
    return out


def barrier_lines(roads):
    """Expressway/trunk lines used for the severance diagnosis."""
    out = []
    for cls in BARRIER_CLASSES:
        out.extend(roads.get(cls, []))
    return out


def walk_ring(station, minutes, speed_mpm=75.0, detour=1.35):
    """Walk-time ring as a reachable area, not a naive circle.

    speed 75 m/min is an ordinary-pedestrian pace; detour 1.35 accounts for
    superblock street pattern. Radius = minutes * speed / detour.
    """
    r = minutes * speed_mpm / detour
    return station["pt"].buffer(r, resolution=64), r

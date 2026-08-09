"""Shared base-map loading and projection for the Haidian rail-TOD drawings.

All geometry is projected to EPSG:32650 (UTM 50N) so distances and walk-time
rings are metric, not degrees.
"""
import json
import math
import os

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
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
    """Area features only. Linear ways are excluded, not closed into polygons.

    The Overpass export mixes both: osm_water.json holds `natural=water` areas
    together with `waterway=river` centrelines. Closing a centreline produces a
    polygon between the river's two ends, and for the culverted 护城河 that is a
    2089 ha slab of blue across 西直门 — a river drawn as a lake covering the
    station it runs past. Rivers belong to load_water_lines().
    """
    out = []
    for e in _ways(os.path.join(DATA, "osm_%s.json" % kind)):
        tags = e.get("tags", {})
        if tags.get("waterway"):
            continue
        geo = e.get("geometry") or []
        pts = [(p["lon"], p["lat"]) for p in geo if p.get("lon") is not None]
        # A ring repeats its first node; an open way does not. Anything that is
        # not closed is a line and cannot be filled.
        if len(pts) < 4 or pts[0] != pts[-1]:
            continue
        try:
            g = prj(shape({"type": "Polygon", "coordinates": [pts]}))
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


_ISO = None


def _isochrones():
    global _ISO
    if _ISO is None:
        p = os.path.join(DATA, "walk_isochrones.json")
        _ISO = json.load(open(p)) if os.path.exists(p) else {"stations": {}}
    return _ISO


def walk_ring(station, minutes, speed_mpm=75.0, detour=1.75):
    """Reachable area for a walking budget, measured where measurement exists.

    For the 7 design-area stations this returns the measured isochrone polygon
    from data/walk_isochrones.json: 16 bearings of real Amap walking routes,
    reduced to the straight-line distance at which route length reaches
    minutes * speed_mpm. Returns (polygon, median_reach_m).

    The circle this replaced used detour=1.35 and was wrong two ways. The
    measured median detour is 1.75, so every ring was drawn too large — the
    seven 15-minute rings covered 1526 ha on paper against 961 ha reachable.
    More importantly the reachable area is not a circle at all: at 学知园 the
    5-minute reach is 284m along the clear bearing and 38m across 京藏高速, so
    no single radius is right. A circle simultaneously overstates the severed
    bearings and understates the open ones, which contradicts this proposal's
    own argument about nominal-versus-actual access.

    The 14 corridor stations were not measured and fall back to a circle at the
    measured median detour of 1.75. That is an estimate, and callers that draw
    it should say so rather than implying the same evidence basis.
    """
    iso = _isochrones()["stations"].get(station.get("name_zh"))
    if iso:
        ring = iso["rings"].get(str(int(minutes)))
        if ring and len(ring["vertices"]) >= 8:
            pts = []
            for bearing, reach in ring["vertices"]:
                # bearing is compass degrees (0 = north, clockwise); the
                # projected CRS is x=east, y=north.
                th = math.radians(90.0 - bearing)
                pts.append((station["x"] + reach * math.cos(th),
                            station["y"] + reach * math.sin(th)))
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0:
                return poly, ring["median_m"]
    r = minutes * speed_mpm / detour
    return station["pt"].buffer(r, resolution=64), r


def is_measured(station):
    """True when this station has a measured isochrone rather than a circle."""
    return station.get("name_zh") in _isochrones()["stations"]


def reach_at(station, minutes, angle_deg):
    """Boundary distance along a math angle (0 = east, CCW), in metres.

    Ring labels used to sit at radius * 1.06, which only works for a circle.
    A measured isochrone varies by bearing, so a fixed radius puts the label
    inside the shape on the long bearings and far outside it on the short ones.
    """
    iso = _isochrones()["stations"].get(station.get("name_zh"))
    if iso:
        ring = iso["rings"].get(str(int(minutes)))
        if ring and ring["vertices"]:
            bearing = (90.0 - angle_deg) % 360.0
            best = min(ring["vertices"],
                       key=lambda v: min(abs(v[0] - bearing),
                                         360 - abs(v[0] - bearing)))
            return best[1]
    return walk_ring(station, minutes)[1]

"""3D bird's-eye views of the 7 per-station-design stations.

One PNG per station: OSM building footprints extruded under a perspective
camera, with the measured walking isochrones lying on the ground plane so the
shape of the reachable area and the built fabric that shapes it appear in the
same image.

Why not Amap's 3D buildings. Amap draws them in its JS API, not through any
REST endpoint, and the JS API refuses this project's key: it is a Web-service
key, and webapi.amap.com answers USERKEY_PLAT_NOMATCH (10009). Amap also
publishes no street-view API, so no panorama is available either. OSM is the
same source as the rest of the base map and is redistributable under ODbL.

What is measured and what is estimated. Footprints are real. Heights mostly are
not: OSM carries `height` or `building:levels` for only a small minority of
buildings here, so the rest are estimated from building type by the table below
and drawn in a paler tone with no roof outline. The count of each is printed on
every sheet. The volumes are context for reading the isochrone shape; they are
not a height survey and must not be read as one.

Run: .venv/bin/python tools/make_3d.py   -> tools/out/figures/3d/*.png
"""
import json
import math
import os

import matplotlib

matplotlib.use("agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Polygon as MplPoly, Rectangle  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, shape  # noqa: E402

import basemap as B  # noqa: E402
import draw as D  # noqa: E402
from station_program import PROGRAM  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out", "figures", "3d")
BUILDINGS = os.path.join(HERE, "data", "osm_buildings.json")
DESIGN = os.path.join(REPO,
                      "submissions/lumixraku/rail-life-rings/geometry/buildings.geojson")

# Estimated storeys by OSM building type, used only where the building carries
# no height tag. Beijing inner-suburb norms: 1980s-90s walk-up slabs at 6, later
# apartment blocks higher, single-storey ancillary structures at 1.
EST_LEVELS = {
    "apartments": 11, "residential": 6, "dormitory": 6, "house": 2,
    "detached": 2, "terrace": 3, "hotel": 12, "office": 8, "commercial": 5,
    "retail": 2, "supermarket": 2, "kiosk": 1, "school": 4, "university": 5,
    "college": 5, "kindergarten": 3, "hospital": 7, "clinic": 3,
    "public": 4, "civic": 4, "government": 6, "train_station": 3,
    "industrial": 2, "warehouse": 2, "service": 1, "garage": 1,
    "garages": 1, "hut": 1, "shed": 1, "roof": 1, "construction": 4,
    "yes": 4,
}
LEVEL_M = 3.2
EST_DEFAULT_LEVELS = 4

RINGS = [(5, "#c0392b"), (10, "#d98324"), (15, "#3f7d54")]

# Camera. South of the station looking north, so north reads up as on the plans.
CAM_AZIMUTH = 180.0
CAM_ELEV = 31.0
FOV_DEG = 46.0
DIST_FACTOR = 2.45      # camera distance as a multiple of the 15-minute max reach
LIGHT = (0.52, -0.62, 0.59)   # from the south-east, well above the horizon


# --- projection -------------------------------------------------------------

def camera_basis(tx, ty, dist):
    """Camera position and orthonormal basis for a station-centred bird's eye."""
    e = math.radians(CAM_ELEV)
    a = math.radians(CAM_AZIMUTH)
    cam = (tx + dist * math.cos(e) * math.sin(a),
           ty + dist * math.cos(e) * math.cos(a),
           dist * math.sin(e))
    fx, fy, fz = (tx - cam[0], ty - cam[1], -cam[2])
    n = math.sqrt(fx * fx + fy * fy + fz * fz)
    fwd = (fx / n, fy / n, fz / n)
    # right = forward x world-up, normalised; world-up is never parallel to
    # forward here because the elevation is well below 90 degrees.
    rx, ry = fwd[1] * 1.0 - 0.0, 0.0 - fwd[0] * 1.0
    n = math.hypot(rx, ry)
    right = (rx / n, ry / n, 0.0)
    up = (right[1] * fwd[2] - right[2] * fwd[1],
          right[2] * fwd[0] - right[0] * fwd[2],
          right[0] * fwd[1] - right[1] * fwd[0])
    return cam, fwd, right, up


class Cam:
    def __init__(self, tx, ty, dist):
        self.cam, self.fwd, self.right, self.up = camera_basis(tx, ty, dist)
        self.k = 1.0 / math.tan(math.radians(FOV_DEG) / 2.0)

    def project(self, x, y, z=0.0):
        vx = x - self.cam[0]
        vy = y - self.cam[1]
        vz = z - self.cam[2]
        d = vx * self.fwd[0] + vy * self.fwd[1] + vz * self.fwd[2]
        if d < 1.0:
            return None
        sx = (vx * self.right[0] + vy * self.right[1]) / d * self.k
        sy = (vx * self.up[0] + vy * self.up[1] + vz * self.up[2]) / d * self.k
        return sx, sy, d

    def path(self, coords, z=0.0):
        """Project a sequence of (x, y); None if any vertex falls behind."""
        out = []
        for x, y in coords:
            p = self.project(x, y, z)
            if p is None:
                return None
            out.append((p[0], p[1]))
        return out


# --- data -------------------------------------------------------------------

def load_buildings():
    if not os.path.exists(BUILDINGS):
        raise SystemExit("missing %s — run tools/fetch_buildings.py first" % BUILDINGS)
    doc = json.load(open(BUILDINGS))
    out = []
    for w in doc["buildings"].values():
        t = w["tags"]
        h, measured = None, False
        raw = t.get("height")
        if raw:
            try:
                h, measured = float(str(raw).split()[0].replace("m", "")), True
            except ValueError:
                h = None
        if h is None and t.get("building:levels"):
            try:
                h = float(str(t["building:levels"]).split(";")[0]) * LEVEL_M
                measured = True
            except ValueError:
                h = None
        if h is None:
            kind = t.get("building") or t.get("building:part") or "yes"
            h = EST_LEVELS.get(kind, EST_DEFAULT_LEVELS) * LEVEL_M
        h = max(3.0, min(h, 180.0))
        ring = B.prj(Polygon(w["pts"])) if len(w["pts"]) >= 4 else None
        if ring is None or not ring.is_valid or ring.area < 40:
            continue
        # Orient CCW so the outward normal of each edge is (dy, -dx).
        coords = list(ring.exterior.coords)[:-1]
        if signed_area(coords) < 0:
            coords.reverse()
        out.append({"coords": coords, "h": h, "measured": measured,
                    "name": t.get("name")})
    return out, doc


def line_label(st):
    """"13 号线 / 昌平线" rather than "13 / 昌平"."""
    out = []
    for ln in st.get("lines") or []:
        s = str(ln)
        out.append("%s 号线" % s if s.isdigit() else s)
    return " / ".join(out)


def signed_area(pts):
    s = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s += x0 * y1 - x1 * y0
    return s / 2.0


def load_design_footprints():
    if not os.path.exists(DESIGN):
        return []
    feats = json.load(open(DESIGN))["features"]
    return [(f["properties"].get("name_zh", ""), B.prj(shape(f["geometry"])))
            for f in feats]


# --- drawing ----------------------------------------------------------------

def shade(base, normal, lo=0.55):
    """Lambert-ish face tone from a world-space normal."""
    d = sum(n * l for n, l in zip(normal, LIGHT))
    f = lo + (1.0 - lo) * max(0.0, d)
    r = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
    return "#%02x%02x%02x" % tuple(min(255, int(c * f + 255 * (1 - f) * 0.35))
                                   for c in r)


def draw_ground(ax, cam, st, rings, roads, barriers, rail, extent_r):
    """Green, water, road and rail bands, then the measured rings, at z = 0."""
    keep = st["pt"].buffer(extent_r)
    for polys, col, a, z in ((B_GREEN, "#e4efe6", 1.0, 2),
                             (B_WATER, "#dbe8f2", 1.0, 3)):
        for g in polys:
            if not g.intersects(keep):
                continue
            g = g.intersection(keep)
            for part in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                if part.is_empty or part.area < 400:
                    continue
                p = cam.path(list(part.exterior.coords))
                if p:
                    ax.add_patch(MplPoly(p, closed=True, fc=col, ec="none",
                                         alpha=a, zorder=z))

    for cls, style in B.ROAD_STYLE.items():
        for ln in roads.get(cls, []):
            if not ln.intersects(keep):
                continue
            seg = ln.intersection(keep)
            for part in (seg.geoms if seg.geom_type == "MultiLineString" else [seg]):
                if part.is_empty or part.length < 8:
                    continue
                p = cam.path(list(part.coords))
                if p:
                    ax.plot([q[0] for q in p], [q[1] for q in p],
                            color=style["color"], lw=style["lw"] * 0.9,
                            solid_capstyle="round", zorder=4)
    # Expressway and trunk carriageways are the reason the rings are lopsided,
    # so they are drawn heavier than their road class alone would give them.
    for ln in barriers:
        if not ln.intersects(keep):
            continue
        seg = ln.intersection(keep)
        for part in (seg.geoms if seg.geom_type == "MultiLineString" else [seg]):
            if part.is_empty or part.length < 8:
                continue
            p = cam.path(list(part.coords))
            if p:
                ax.plot([q[0] for q in p], [q[1] for q in p],
                        color="#8f959d", lw=4.2, alpha=0.85,
                        solid_capstyle="round", zorder=5)
    for ln in rail:
        if not ln.intersects(keep):
            continue
        seg = ln.intersection(keep)
        for part in (seg.geoms if seg.geom_type == "MultiLineString" else [seg]):
            if part.is_empty or part.length < 8:
                continue
            p = cam.path(list(part.coords))
            if p:
                ax.plot([q[0] for q in p], [q[1] for q in p],
                        color=D.C["rail"], lw=1.9, alpha=0.9, zorder=6)

    for mins, col in RINGS:
        poly, med = B.walk_ring(st, mins)
        p = cam.path(list(poly.exterior.coords))
        if p:
            ax.add_patch(MplPoly(p, closed=True, fc=col, ec=col, lw=1.5,
                                 alpha=0.13, zorder=7))
            ax.plot([q[0] for q in p], [q[1] for q in p], color=col, lw=1.6,
                    alpha=0.95, zorder=8)
        # The circle the ring replaced, dashed, so the overstatement is shown
        # rather than asserted.
        former = rings[str(mins)]["former_circle_m"]
        c = cam.path(list(st["pt"].buffer(former, resolution=72).exterior.coords))
        if c:
            ax.plot([q[0] for q in c], [q[1] for q in c], color=col, lw=0.9,
                    ls=(0, (4, 3)), alpha=0.75, zorder=8)


def draw_buildings(ax, cam, blds, extent_r, st):
    """Extrude footprints, far to near, with only camera-facing walls."""
    keep = st["pt"].buffer(extent_r)
    items = []
    for b in blds:
        c = b["coords"]
        cx = sum(p[0] for p in c) / len(c)
        cy = sum(p[1] for p in c) / len(c)
        if not keep.contains(Point(cx, cy)):
            continue
        p = cam.project(cx, cy, 0.0)
        if p is None:
            continue
        items.append((p[2], b))
    items.sort(key=lambda t: -t[0])

    # Painter's order needs one z per building, but the band must stay bounded:
    # at 500+ buildings a plain 20+i runs past the ring overlay at 300 and the
    # note at 500, and the near facades then paint over the annotation.
    n_meas = 0
    span = 200.0 / max(1, len(items))
    for i, (_, b) in enumerate(items):
        z = 20.0 + i * span
        coords, h = b["coords"], b["h"]
        wall_base = "#b9bec6" if b["measured"] else "#cfd3d8"
        roof_base = "#8f96a0" if b["measured"] else "#b6bbc2"
        if b["measured"]:
            n_meas += 1
        walls = []
        for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1]):
            dx, dy = x1 - x0, y1 - y0
            L = math.hypot(dx, dy)
            if L < 0.5:
                continue
            nx, ny = dy / L, -dx / L
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            v = cam.project(mx, my, h / 2)
            if v is None:
                continue
            # Facing the camera when the outward normal opposes the view ray.
            ray = (mx - cam.cam[0], my - cam.cam[1])
            if nx * ray[0] + ny * ray[1] >= 0:
                continue
            quad = [cam.project(x0, y0, 0.0), cam.project(x1, y1, 0.0),
                    cam.project(x1, y1, h), cam.project(x0, y0, h)]
            if any(q is None for q in quad):
                continue
            walls.append((v[2], [(q[0], q[1]) for q in quad],
                          shade(wall_base, (nx, ny, 0.0))))
        walls.sort(key=lambda t: -t[0])
        for j, (_, quad, col) in enumerate(walls):
            ax.add_patch(MplPoly(quad, closed=True, fc=col, ec=col,
                                 lw=0.15, zorder=z + j * 0.001))
        roof = cam.path(coords, h)
        if roof:
            ax.add_patch(MplPoly(roof, closed=True, fc=shade(roof_base, (0, 0, 1)),
                                 ec="#7d848e" if b["measured"] else "none",
                                 lw=0.3 if b["measured"] else 0.0,
                                 zorder=z + 0.5))
    return len(items), n_meas


def ring_overlay(ax, cam, st, rings):
    """Re-trace the ring outlines above the volumes.

    The rings belong on the ground, but at this pitch the buildings cover most
    of them and the boundary is the whole point of the sheet. So the outline is
    drawn a second time over the massing at reduced opacity: the shape stays
    readable while still reading as something lying on the ground rather than
    floating above it.
    """
    for mins, col in RINGS:
        poly, _ = B.walk_ring(st, mins)
        p = cam.path(list(poly.exterior.coords))
        if p:
            ax.plot([q[0] for q in p], [q[1] for q in p], color=col, lw=1.5,
                    alpha=0.62, zorder=300, solid_capstyle="round")
        circ = st["pt"].buffer(rings[str(mins)]["former_circle_m"], resolution=72)
        c = cam.path(list(circ.exterior.coords))
        if c:
            ax.plot([q[0] for q in c], [q[1] for q in c], color=col, lw=0.85,
                    ls=(0, (4, 3)), alpha=0.5, zorder=300)


# Candidate directions for a ring label, as math angles (0 = east, CCW) to match
# reach_at. Tried in order: north first so the labels read the same way as the
# plans, then round the compass.
LABEL_ANGLES = (90.0, 112.5, 67.5, 135.0, 45.0, 157.5, 22.5, 180.0, 0.0)


def ring_labels(ax, cam, st, rings):
    """Minute labels on each ring boundary, spread so they do not stack.

    A fixed bearing does not work: where a station is severed the short rings
    are only tens of metres out, so north-anchored labels for 5 and 10 minutes
    land on top of each other and on the station name. Placement is therefore
    chosen in screen space, which is also the only space where "do these two
    labels overlap" is a meaningful question under perspective.
    """
    # The station name sits on top of a 118m pole above the station point.
    taken = []
    top = cam.project(st["x"], st["y"], 118.0)
    if top:
        taken.append((top[0], top[1]))
    span = max(abs(p[0]) for p in
               (cam.path(list(B.walk_ring(st, 15)[0].exterior.coords)) or [(1, 1)]))
    min_gap = span * 0.20

    for mins, col in RINGS:
        placed = None
        for angle in LABEL_ANGLES:
            reach = B.reach_at(st, mins, angle)
            th = math.radians(angle)
            p = cam.project(st["x"] + reach * math.cos(th),
                            st["y"] + reach * math.sin(th), 0.0)
            if p is None:
                continue
            if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= min_gap for q in taken):
                placed = p
                break
        if placed is None:
            continue
        taken.append((placed[0], placed[1]))
        ax.text(placed[0], placed[1],
                "%d 分钟 中位 %d 米" % (mins, round(rings[str(mins)]["median_m"])),
                fontproperties=D.font(5.6, "bold"), color=col, ha="center",
                va="center", zorder=320,
                bbox=dict(fc="#ffffffe0", ec=col, lw=0.5, pad=1.7))


def draw_design(ax, cam, st, extent_r):
    """Proposal footprints from the submission geometry, if any fall in frame."""
    keep = st["pt"].buffer(extent_r)
    n = 0
    for name, g in DESIGN_FOOT:
        if not g.intersects(keep):
            continue
        for part in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
            p = cam.path(list(part.exterior.coords), 0.4)
            if p:
                ax.add_patch(MplPoly(p, closed=True, fc=D.C["life"], ec=D.C["life"],
                                     lw=1.2, alpha=0.42, zorder=15))
                n += 1
    return n


def station_marker(ax, cam, st):
    p = cam.project(st["x"], st["y"], 0.0)
    top = cam.project(st["x"], st["y"], 118.0)
    if p and top:
        ax.plot([p[0], top[0]], [p[1], top[1]], color=D.C["ink"], lw=1.0,
                alpha=0.8, zorder=400)
        ax.plot([top[0]], [top[1]], marker="o", ms=5.0, mfc=D.C["life"],
                mec="#ffffff", mew=1.1, zorder=401)
        ax.plot([p[0]], [p[1]], marker="o", ms=3.2, mfc=D.C["ink"],
                mec="none", zorder=401)
        ax.text(top[0], top[1] + 0.012, st["name_zh"],
                fontproperties=D.font(7.4, "bold"), color=D.C["ink"],
                ha="center", va="bottom", zorder=402,
                bbox=dict(fc="#ffffffdd", ec="none", pad=1.6))


# --- sheet ------------------------------------------------------------------

def sheet(st, iso, blds):
    rings = iso["rings"]
    reach_max = max(r["max_m"] for r in rings.values())
    extent_r = min(1150.0, reach_max * 1.30)
    dist = reach_max * DIST_FACTOR

    W, H = 300.0, 200.0
    D.SCALE = W / 210.0
    fig = plt.figure(figsize=(W * D.MM, H * D.MM), dpi=190)
    fig.patch.set_facecolor(D.C["paper"])

    head = fig.add_axes([0, 0, 1, 1])
    head.set_axis_off()
    head.set_xlim(0, 1)
    head.set_ylim(0, 1)
    head.add_patch(Rectangle((0, 0.918), 1, 0.082, color=D.C["band"], zorder=0))
    head.text(0.016, 0.968, "%s　站域三维鸟瞰" % st["name_zh"],
              fontproperties=D.font(11.5, "bold"), color=D.C["ink"], va="center")
    head.text(0.016, 0.936,
              "实测步行等时圈落在地面，OSM 建筑体量为空间参照；虚线为原同心圆",
              fontproperties=D.font(6.4), color=D.C["mute"], va="center")
    # Spelled out, not bare "27": a bare number in a sheet corner reads as a
    # page number.
    head.text(0.984, 0.955, line_label(st),
              fontproperties=D.font(6.2), color=D.C["rail"], ha="right",
              va="center")

    ax = fig.add_axes([0.008, 0.045, 0.700, 0.865])
    ax.set_axis_off()
    ax.set_facecolor("#f8fafb")
    ax.set_aspect("equal")

    cam = Cam(st["x"], st["y"], dist)
    draw_ground(ax, cam, st, rings, ROADS, BARRIERS, RAIL, extent_r)
    n_bld, n_meas = draw_buildings(ax, cam, blds, extent_r, st)
    n_design = draw_design(ax, cam, st, extent_r)
    ring_overlay(ax, cam, st, rings)
    ring_labels(ax, cam, st, rings)
    station_marker(ax, cam, st)

    frame(ax, cam, st, rings, W * 0.700, H * 0.865)

    # White plate under the note: at this pitch the near buildings reach the
    # bottom of the frame, and without it the text sits inside a facade.
    ax.text(0.010, 0.014,
            "视点：站点正南 %.0f 米、仰角 %.0f°、视场 %.0f°，正北朝画面上方。竖向未夸大"
            % (dist * math.cos(math.radians(CAM_ELEV)), CAM_ELEV, FOV_DEG),
            transform=ax.transAxes, fontproperties=D.font(5.2),
            color=D.C["mute"], va="bottom", zorder=500,
            bbox=dict(fc="#ffffffdc", ec="none", pad=2.2))

    panel(fig, st, rings, n_bld, n_meas, n_design)

    path = os.path.join(OUT, "%s.png" % SLUG[st["name_zh"]])
    fig.savefig(path, dpi=190, facecolor=D.C["paper"])
    plt.close(fig)
    return path, n_bld, n_meas


def frame(ax, cam, st, rings, w_mm, h_mm):
    """Crop to the widest thing on the ground, at the axes aspect.

    The widest thing is the 15-minute dashed circle, not the measured ring: the
    circle is larger on the severed bearings, so framing on the ring alone cuts
    it off. Framing on the union of both keeps every sheet at the same crop
    logic, and a perspective view needs the extent measured in screen space
    because a ground circle projects to an ellipse.
    """
    pts = []
    for mins, _ in RINGS:
        poly, _ = B.walk_ring(st, mins)
        pts += cam.path(list(poly.exterior.coords)) or []
        circ = st["pt"].buffer(rings[str(mins)]["former_circle_m"], resolution=72)
        pts += cam.path(list(circ.exterior.coords)) or []
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = 0.055
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    x0, x1, y0, y1 = x0 - dx, x1 + dx, y0 - dy, y1 + dy
    # Expand the short side to the panel aspect so nothing is squeezed and the
    # tall building tops above the far ring stay in frame.
    aspect = h_mm / w_mm
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    if h / w < aspect:
        h = w * aspect
    else:
        w = h / aspect
    ax.set_xlim(cx - w / 2, cx + w / 2)
    ax.set_ylim(cy - h / 2, cy + h / 2)


def panel(fig, st, rings, n_bld, n_meas, n_design):
    ax = fig.add_axes([0.716, 0.045, 0.272, 0.865])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0, 0), 1, 1, fc="#fbfcfd", ec=D.C["hair"], lw=0.7))

    y = 0.962
    ax.text(0.05, y, "实测可达距离", fontproperties=D.font(7.6, "bold"),
            color=D.C["ink"], va="top")
    y -= 0.036
    ax.text(0.05, y, "16 方位高德步行路径反算（2026-08-09）",
            fontproperties=D.font(5.0), color=D.C["mute"], va="top")
    y -= 0.040
    for mins, col in RINGS:
        r = rings[str(mins)]
        ax.plot([0.05, 0.11], [y - 0.012, y - 0.012], color=col, lw=2.2,
                solid_capstyle="butt")
        ax.text(0.14, y, "%d 分钟" % mins, fontproperties=D.font(6.6, "bold"),
                color=col, va="top")
        y -= 0.030
        ax.text(0.14, y, "中位 %d 米　范围 %d–%d 米"
                % (round(r["median_m"]), round(r["min_m"]), round(r["max_m"])),
                fontproperties=D.font(5.6), color=D.C["ink"], va="top")
        y -= 0.027
        d = round(100.0 * (r["median_m"] - r["former_circle_m"]) / r["former_circle_m"])
        ax.text(0.14, y, "原同心圆 %d 米（中位差 %+d%%）"
                % (r["former_circle_m"], d),
                fontproperties=D.font(5.2), color=D.C["mute"], va="top")
        y -= 0.038

    y -= 0.012
    r15 = rings["15"]
    ratio = r15["max_m"] / max(1.0, r15["min_m"])
    ax.plot([0.05, 0.95], [y, y], color=D.C["hair"], lw=0.7)
    y -= 0.030
    ax.text(0.05, y, "为什么不是圆", fontproperties=D.font(7.0, "bold"),
            color=D.C["ink"], va="top")
    y -= 0.034
    body = ("同一站 15 分钟内最长与最短方位相差 %.1f 倍（%d 米 / %d 米）。"
            "差距来自快速路、铁路与围墙，不是距离本身。"
            % (ratio, round(r15["max_m"]), round(r15["min_m"])))
    for line in D.wrap_cjk(body, 21):
        ax.text(0.05, y, line, fontproperties=D.font(5.5), color=D.C["ink"],
                va="top")
        y -= 0.026

    y -= 0.016
    ax.plot([0.05, 0.95], [y, y], color=D.C["hair"], lw=0.7)
    y -= 0.030
    ax.text(0.05, y, "图例与体量说明", fontproperties=D.font(7.0, "bold"),
            color=D.C["ink"], va="top")
    y -= 0.036
    legend = [
        ("#8f96a0", "有高度标签的建筑（%d 栋，屋顶描边）" % n_meas),
        ("#c3c8ce", "高度按类型估算（%d 栋，仅供判读）" % (n_bld - n_meas)),
        ("#8f959d", "快速路与主干道，站域切割来源"),
        (D.C["rail"], "轨道线路"),
    ]
    if n_design:
        legend.append((D.C["life"], "本方案建筑原型占地（%d 处）" % n_design))
    for col, txt in legend:
        ax.add_patch(Rectangle((0.05, y - 0.019), 0.055, 0.019, fc=col,
                               ec="none"))
        for k, line in enumerate(D.wrap_cjk(txt, 17)):
            ax.text(0.125, y - k * 0.024, line, fontproperties=D.font(5.2),
                    color=D.C["ink"], va="top")
        y -= 0.024 * max(1, len(D.wrap_cjk(txt, 17))) + 0.008

    y -= 0.010
    ax.plot([0.05, 0.95], [y, y], color=D.C["hair"], lw=0.7)
    y -= 0.028
    note = ("建筑轮廓来自 OpenStreetMap（ODbL 1.0）。高度只有 %d/%d 栋有标签，"
            "其余按建筑类型估算，图面用浅色区分；体量供空间关系判读，不作为高度依据。"
            "高德 3D 建筑需 Web端(JS API) 密钥，本项目密钥为 Web 服务类型，"
            "接口返回 USERKEY_PLAT_NOMATCH，故未采用；高德亦无对外街景接口。"
            % (n_meas, n_bld))
    for line in D.wrap_cjk(note, 22):
        ax.text(0.05, y, line, fontproperties=D.font(4.7), color=D.C["mute"],
                va="top")
        y -= 0.022


SLUG = {
    "学知园": "3d-xuezhiyuan", "六道口": "3d-liudaokou",
    "学院桥": "3d-xueyuanqiao", "西土城": "3d-xitucheng",
    "蓟门桥": "3d-jimenqiao", "北京北": "3d-beijingbei",
    "西直门": "3d-xizhimen",
}


def main():
    global ROADS, BARRIERS, RAIL, B_GREEN, B_WATER, DESIGN_FOOT
    os.makedirs(OUT, exist_ok=True)
    ROADS = B.load_roads()
    BARRIERS = B.barrier_lines(ROADS)
    heavy, metro = B.load_rail()
    RAIL = heavy + metro
    B_GREEN = B.load_polys("green")
    B_WATER = B.load_polys("water")
    DESIGN_FOOT = load_design_footprints()

    blds, doc = load_buildings()
    print("buildings loaded: %d (%d with height tag)"
          % (len(blds), sum(1 for b in blds if b["measured"])))

    iso = B._isochrones()["stations"]
    stations = {s["name_zh"]: s for s in B.load_stations()}
    for name in SLUG:
        st = stations[name]
        path, n, m = sheet(st, iso[name], blds)
        print("%-6s %-26s %3d buildings, %d tagged"
              % (name, os.path.basename(path), n, m))


if __name__ == "__main__":
    main()

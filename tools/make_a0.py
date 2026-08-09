"""True-A0 boards (841 x 1189 mm), vector, with a real text layer.

The station is the unit of the drawing set, not the key area:

L-01       corridor structure + all 21 stations, scope levels
L-02..L-08 one full plate per design-area station (7 plates)
L-09       key-area prototypes + phasing + the 大钟寺 polygon discrepancy

The earlier version put all 7 stations in a 3x3 grid on a single plate, which
gave each station one small cell — a station index, not per-station design.
The severance diagnosis that used to be its own plate is now folded into each
station's own plate, because severance is inherently a per-station problem.
"""
import math
import os

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

import basemap as B
import draw as D
from station_program import CORRIDOR_ROLE, PROGRAM

PAGE = "A0"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

bd = B.load_boundaries()
roads = B.load_roads()
heavy, metro = B.load_rail()
green = B.load_polys("green")
water = B.load_polys("water")
rivers = B.load_water_lines()
stations = B.load_stations()
barriers = B.barrier_lines(roads)

SITE = bd["PROV-SITE-001"]
RESEARCH = bd["PROV-RESEARCH-001"]
KEYS = {k: bd[k] for k in ("PROV-KEY-001", "PROV-KEY-002", "PROV-KEY-003")}
DESIGN = [s for s in stations if s["scope_level"] == "overall_design_area"]
CORR = [s for s in stations if s["scope_level"] != "overall_design_area"]


def pad_extent(geom, pad=0.10):
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    return (minx - w * pad, miny - h * pad, maxx + w * pad, maxy + h * pad)


def draw_boundaries(ax, show_research=True):
    S = D.SCALE
    if show_research:
        xs, ys = RESEARCH.exterior.xy
        ax.plot(xs, ys, color=D.C["mute"], lw=1.0 * S, dashes=(7, 5), zorder=6)
    xs, ys = SITE.exterior.xy
    ax.plot(xs, ys, color=D.C["ink"], lw=1.7 * S, zorder=7)
    for k, g in KEYS.items():
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color=D.C["life"], alpha=0.10, ec="none", zorder=1.5)
        ax.plot(xs, ys, color=D.C["life"], lw=1.3 * S, zorder=7)


def station_dot(ax, s, r_pt=5.0, core=False):
    col = D.C["rail"] if s["mode"] == "subway" else D.C["ink"]
    S = D.SCALE
    ax.plot([s["x"]], [s["y"]], marker="o", ms=r_pt * S,
            mfc="white", mec=col, mew=(1.6 if core else 1.1) * S, zorder=20)
    if core:
        ax.plot([s["x"]], [s["y"]], marker="o", ms=r_pt * 0.42 * S,
                mfc=col, mec="none", zorder=21)


def legend(ax, items, x, y, page_ts=1.0, size=7.2, title=None, gap=None,
           lp=None, panel_w=None):
    """Explicit legend. Every symbol on the sheet must be decodable.

    The panel behind it is not decoration: without it the ring fills and road
    strokes run straight through the label text. Pass `lp` to also reserve the
    footprint in the label placer so station names cannot land underneath.
    """
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    px = x0 + (x1 - x0) * x
    py = y0 + (y1 - y0) * y
    step = gap if gap else (y1 - y0) * 0.026
    n_rows = len(items) + (1 if title else 0)
    pad_x = (x1 - x0) * 0.010
    pad_y = step * 0.55
    if panel_w is None:
        # measure the longest label instead of hand-setting a width: a longer
        # legend entry used to run straight out of its own white panel
        px_per_pt = ax.figure.dpi / 72.0
        upp_x = (x1 - x0) / max(ax.get_window_extent().width, 1.0)
        widest = 0.0
        for _, label in items:
            n_cjk = sum(1 for ch in label if ord(ch) > 0x2E80)
            widest = max(widest, size * D.SCALE
                         * (n_cjk + 0.55 * (len(label) - n_cjk)))
        pw_d = widest * px_per_pt * upp_x + (x1 - x0) * 0.048
    else:
        pw_d = (x1 - x0) * panel_w
    ph_d = n_rows * step
    ax.add_patch(Rectangle((px - pad_x, py + pad_y - ph_d), pw_d, ph_d,
                           fc="white", alpha=0.90, ec=D.C["hair"],
                           lw=0.9 * D.SCALE, zorder=69))
    if lp is not None:
        lp.reserve(px - pad_x, py + pad_y - ph_d, px - pad_x + pw_d,
                   py + pad_y)
    if title:
        ax.text(px, py, title, fontproperties=D.font(size * 1.05, "bold"),
                color=D.C["ink"], va="center", zorder=71)
        py -= step
    for handle, label in items:
        if handle["kind"] == "line":
            kw = dict(color=handle["c"], lw=handle.get("lw", 1.4) * D.SCALE, zorder=71,
                      solid_capstyle="round")
            if handle.get("dashes"):
                kw["dashes"] = handle["dashes"]
            ax.plot([px, px + (x1 - x0) * 0.022], [py, py], **kw)
        elif handle["kind"] == "patch":
            w = (x1 - x0) * 0.022
            h = step * 0.5
            ax.add_patch(Rectangle((px, py - h / 2), w, h, fc=handle["c"],
                                   alpha=handle.get("alpha", 1.0),
                                   ec=handle.get("ec", "none"), lw=0.8 * D.SCALE, zorder=71))
        else:
            ax.plot([px + (x1 - x0) * 0.011], [py], marker="o", ms=handle.get("ms", 5) * D.SCALE,
                    mfc=handle.get("mfc", "white"), mec=handle["c"],
                    mew=1.4 * D.SCALE, zorder=71)
        ax.text(px + (x1 - x0) * 0.030, py, label, fontproperties=D.font(size),
                color=D.C["ink"], va="center", zorder=71)
        py -= step


# ---------------------------------------------------------------- plate 1
def plate1(pdf, total):
    fig, pw, ph = D.new_page(PAGE)
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "京张轨道生活环 · 廊道结构与站点体系",
        "总体设计范围 11.4平方公里 / 统筹研究范围 43.6平方公里 · 21 座轨道站的分级设计深度",
        "L-01", "L-%02d" % total)

    # The site is a tall N-S strip, so a full-width map wastes half the sheet.
    # Map takes the left column at its natural aspect; ledger takes the right.
    body_h = ph - 2 * m - 78
    map_w = (pw - 2 * m - 16) * 0.52
    led_w = (pw - 2 * m - 16) - map_w - 18
    top = D.ax_at(fig, m + 8, m + 30, map_w, body_h, PAGE)
    D.clean(top)
    ext = pad_extent(RESEARCH, 0.06)
    D.draw_base(top, roads, heavy, metro, green, water, rivers, ext, lw_scale=1.5)
    draw_boundaries(top)

    lp = D.LabelPlacer(top)
    legend(top, [
        ({"kind": "dot", "c": D.C["rail"], "ms": 7}, "设计范围内站点：逐站详细设计（7座）"),
        ({"kind": "dot", "c": D.C["mute"], "ms": 5}, "研究范围内站点：廊道与接驳层级（14座）"),
        ({"kind": "line", "c": D.C["ink"], "lw": 1.7}, "总体设计范围 11.4平方公里"),
        ({"kind": "line", "c": D.C["mute"], "lw": 1.0, "dashes": (7, 5)}, "统筹研究范围 43.6平方公里"),
        ({"kind": "patch", "c": D.C["life"], "alpha": 0.25, "ec": D.C["life"]}, "三处重点区域 368.4ha"),
        ({"kind": "line", "c": D.C["ink"], "lw": 1.5}, "国铁 / 市郊铁路（京张）"),
        ({"kind": "line", "c": D.C["rail"], "lw": 0.9}, "地铁线路"),
        ({"kind": "line", "c": "#8a8f98", "lw": 2.4}, "高速与快速路（切割源）"),
    ], 0.015, 0.365, title="图例", size=8.0, lp=lp)

    for s in DESIGN:
        station_dot(top, s, 7.5, core=True)
    for s in CORR:
        station_dot(top, s, 5.0)
    # label design-area stations first so they win the collision search
    for s in DESIGN:
        lp.place(s["x"], s["y"], "%s %s" % (s["name_zh"], "/".join(s["lines"]) or "S"),
                 size=9.2, weight="bold", color=D.C["ink"])
    for s in CORR:
        lp.place(s["x"], s["y"], s["name_zh"], size=6.8, color=D.C["mute"],
                 force=True)

    # key-area labels go through the same placer so they cannot land on top of
    # a station label; anchor to the polygon's west edge, clear of the strip
    for k, g in KEYS.items():
        c = g.centroid
        lp.place(g.bounds[0], c.y, B.KEY_LABELS[k], size=9.6, weight="bold",
                 color=D.C["life"],
                 prefer=[("right", "center", -(ext[2] - ext[0]) * 0.012, 0),
                         ("right", "bottom", -(ext[2] - ext[0]) * 0.012,
                          (ext[3] - ext[1]) * 0.008),
                         ("right", "top", -(ext[2] - ext[0]) * 0.012,
                          -(ext[3] - ext[1]) * 0.008)])
    D.scale_bar(top, 2000, "2km")
    D.north_arrow(top)

    # Right column: the station ledger. Split into two fitted panels — a single
    # hand-positioned run overflowed the footer as soon as entries got taller,
    # and cut off the last corridor stations silently.
    led_gap = 22
    led_top_h = body_h * 0.60
    led_bot_h = body_h - led_top_h - led_gap
    led_x = m + 8 + map_w + 18

    tb = D.ax_at(fig, led_x, m + 30 + led_bot_h + led_gap, led_w, led_top_h,
                 PAGE)
    D.clean(tb, frame=False)
    tb.set_xlim(0, 1)
    tb.set_ylim(0, 1)
    blocks = [
        (0.0, "站点分级台账", 13.5, D.C["ink"], "bold", 0.012),
        (0.0, "分级依据：官方公告四至（北至北五环路、东至京藏高速与学院路、"
              "南至西直门外大街、西至万泉河路与大钟寺东路），对每座车站逐一做"
              "点面判定。站位取自 OpenStreetMap，属概念定位；7 座逐站设计车站的"
              "站域已按高德步行路径实测为等时圈，出入口位置仍须以实测替换。",
         7.6, D.C["mute"], "normal", 0.014),
        (0.0, "总体设计范围内 · 逐站详细设计（7座）", 10.5, D.C["rail"], "bold",
         0.014),
    ]
    for s in DESIGN:
        p = PROGRAM[s["name_zh"]]
        ka = s["key_area"] or ("近%s %.0fm" % (s["nearest_key_area"],
                                              s["nearest_key_area_distance_m"]))
        blocks += [
            (0.0, "%s %s · %s" % (s["name_zh"], "/".join(s["lines"]) or "S5",
                                  ka), 9.4, D.C["rail"], "bold", 0.004),
            (0.02, p["role"], 8.0, D.C["ink"], "bold", 0.003),
            (0.02, "现状问题：" + p["problem"], 7.2, D.C["warn"], "normal",
             0.003),
            (0.02, "近期动作：" + "；".join(p["moves"]), 7.2, D.C["park"],
             "normal", 0.010),
        ]
    D.fit_blocks(tb, blocks, 0.995, 0.01)

    cb = D.ax_at(fig, led_x, m + 30, led_w, led_bot_h, PAGE)
    D.clean(cb, frame=False)
    cb.set_xlim(0, 1)
    cb.set_ylim(0, 1)
    cblocks = [(0.0, "统筹研究范围内 · 廊道与接驳层级（14座）", 10.5,
                D.C["mute"], "bold", 0.014)]
    for s in CORR:
        # name and role on one fitted block: 清华东路西口 overruns any fixed x
        cblocks.append((0.0, "%s %s　%s" % (s["name_zh"], "/".join(s["lines"]),
                                           CORRIDOR_ROLE.get(s["name_zh"], "")),
                        7.4, D.C["ink"], "normal", 0.006))
    D.fit_blocks(cb, cblocks, 0.995, 0.01)

    pdf.savefig(fig)
    fig.clf()


# ------------------------------------------- plates 2..8: one plate per station
def plate_station(pdf, s, idx, total):
    """One full A0 plate for a single station.

    The old version put all seven stations in a 3x3 grid on one sheet, which
    gave each station a cell the size of a postcard — a station index, not
    per-station design. The severance diagnosis that used to be its own plate
    is folded in here, because severance is inherently per-station: the
    barrier that matters at 学知园 (京藏高速 + 北五环) is not the one that
    matters at 西直门.
    """
    fig, pw, ph = D.new_page(PAGE)
    p = PROGRAM[s["name_zh"]]
    mode = "地铁" if s["mode"] == "subway" else "国铁 / 市郊铁路"
    lines_txt = "/".join(s["lines"]) or "S5"
    line_label = ("%s号线" % lines_txt) if s["mode"] == "subway" else lines_txt
    ka = s["key_area"] or ("近%s %.0fm" % (s["nearest_key_area"],
                                          s["nearest_key_area_distance_m"]))
    # Measured isochrones vary by bearing, so a single "278m" in the legend
    # would be a false claim. Report median and the observed spread.
    rng = {}
    for mins in (5, 10, 15):
        poly, med = B.walk_ring(s, mins)
        rs = [B.reach_at(s, mins, a) for a in range(0, 360, 22)]
        rng[mins] = (round(med), round(min(rs)), round(max(rs)))
    r5, r10, r15v = rng[5][0], rng[10][0], rng[15][0]

    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "%s站 · %s" % (s["name_zh"], p["role"]),
        "%s · %s · %s · 5/10/15 分钟站域、切割诊断、功能配置与近期动作"
        % (line_label, mode, ka),
        "L-%02d" % idx, "L-%02d" % total)

    # --- sheet layout, in millimetres from the bottom-left -----------------
    body_top = ph - m - 46
    body_bot = m + 26
    gap_v = 20
    x0 = m + 8
    bw = pw - 2 * m - 16
    map_h = (body_top - body_bot - gap_v) * 0.58
    col_h = (body_top - body_bot - gap_v) - map_h
    map_y = body_top - map_h

    # --- station-area map ---------------------------------------------------
    ax = D.ax_at(fig, x0, map_y, bw, map_h, PAGE)
    D.clean(ax)
    ring15 = B.walk_ring(s, 15)[0]
    ext = D.fit_extent(pad_extent(ring15, 0.30), bw, map_h)
    D.draw_base(ax, roads, heavy, metro, green, water, rivers, ext,
                show_tertiary=True, lw_scale=1.8)

    for k, g in KEYS.items():
        if not g.intersects(ring15):
            continue
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color=D.C["life"], alpha=0.12, ec="none", zorder=1.5)
        ax.plot(xs, ys, color=D.C["life"], lw=1.6 * D.SCALE, zorder=7)

    # dashed, and below the station dots: a solid boundary drawn over 西直门
    # hid the dot the whole sheet is about
    xs, ys = SITE.exterior.xy
    ax.plot(xs, ys, color=D.C["ink"], lw=1.4 * D.SCALE, dashes=(9, 5),
            alpha=0.85, zorder=6.5)

    for mins, alpha in ((15, 0.07), (10, 0.11), (5, 0.17)):
        ring = B.walk_ring(s, mins)[0]
        xs, ys = ring.exterior.xy
        ax.fill(xs, ys, color=D.C["rail"], alpha=alpha, ec="none", zorder=8)
        ax.plot(xs, ys, color=D.C["rail"], lw=1.0 * D.SCALE, alpha=0.7,
                zorder=8.5)

    # Severance, two tiers. Grade-separated expressways (motorway/trunk) are
    # hard breaks; wide at-grade arterials (primary) are crossable but cost
    # signal wait. Showing only the first tier printed "0 段" at 六道口, whose
    # own diagnosis names 学院路 — an arterial OSM classes as primary.
    cut = [ln for ln in barriers if ln.intersects(ring15)]
    arter = [ln for ln in roads.get("primary", []) if ln.intersects(ring15)]
    for ln in arter:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=1.8 * D.SCALE, alpha=0.55,
                dashes=(6, 4), zorder=8.8)
    for ln in cut:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=3.0 * D.SCALE, alpha=0.8,
                zorder=9)

    lp = D.LabelPlacer(ax)
    # the legend must claim its footprint before any label is placed, or the
    # reservation arrives after the collision search has already run
    legend(ax, [
        ({"kind": "dot", "c": D.C["rail"] if s["mode"] == "subway"
          else D.C["ink"], "ms": 9}, "本站：%s" % s["name_zh"]),
        ({"kind": "dot", "c": D.C["mute"], "ms": 6}, "邻近轨道站"),
        ({"kind": "patch", "c": D.C["rail"], "alpha": 0.35},
         "5分钟实测 中位%dm（%d-%dm）" % rng[5]),
        ({"kind": "patch", "c": D.C["rail"], "alpha": 0.22},
         "10分钟实测 中位%dm（%d-%dm）" % rng[10]),
        ({"kind": "patch", "c": D.C["rail"], "alpha": 0.14},
         "15分钟实测 中位%dm（%d-%dm）" % rng[15]),
        ({"kind": "line", "c": D.C["warn"], "lw": 3.0},
         "立体切割：高速/快速路（%d 段）" % len(cut)),
        ({"kind": "line", "c": D.C["warn"], "lw": 1.8, "dashes": (6, 4)},
         "平面切割：主干路，可过街但有信号延误（%d 段）" % len(arter)),
        ({"kind": "patch", "c": D.C["life"], "alpha": 0.30,
          "ec": D.C["life"]}, "重点区域（provisional）"),
        ({"kind": "line", "c": D.C["ink"], "lw": 1.4, "dashes": (9, 5)},
         "总体设计范围边界"),
    ], 0.014, 0.40, size=9.0, title="图例", lp=lp)

    station_dot(ax, s, 14.0, core=True)
    # the sheet's subject: never drop this one
    lp.place(s["x"], s["y"], "%s %s" % (s["name_zh"], line_label),
             size=15.0, weight="bold", force=True)

    # ring radii on three separate bearings; a shared baseline is what made
    # the old raster figures unreadable
    for mins, r, ang in ((5, r5, 96), (10, r10, 210), (15, r15v, 330)):
        # anchor just outside the boundary on this bearing, not on it: sitting
        # exactly on it put the stroke through the middle of the text. The
        # boundary distance is bearing-specific now, so a fixed radius would
        # land inside the shape on long bearings.
        rr = B.reach_at(s, mins, ang) * 1.06
        lx = s["x"] + rr * math.cos(math.radians(ang))
        ly = s["y"] + rr * math.sin(math.radians(ang))
        lp.place(lx, ly, "%d分钟 中位%dm" % (mins, r), size=10.0, weight="bold",
                 color=D.C["rail"])

    near = [o for o in stations
            if o is not s and ring15.buffer(900).contains(o["pt"])]
    for o in near:
        station_dot(ax, o, 6.5)
    for o in near:
        lp.place(o["x"], o["y"], o["name_zh"], size=8.2, color=D.C["mute"],
                 force=True)

    for k, g in KEYS.items():
        if g.intersects(ring15):
            lp.place(g.centroid.x, g.centroid.y, B.KEY_LABELS[k], size=10.0,
                     weight="bold", color=D.C["life"])

    D.scale_bar(ax, 500, "500m")
    D.north_arrow(ax)

    # --- three text columns: diagnosis / programme / actions ---------------
    gap_h = 16
    cw = (bw - 2 * gap_h) / 3

    def column(i):
        cx = D.ax_at(fig, x0 + i * (cw + gap_h), body_bot, cw, col_h, PAGE)
        D.clean(cx, frame=False)
        cx.set_xlim(0, 1)
        cx.set_ylim(0, 1)
        return cx

    c1 = column(0)
    D.fit_blocks(c1, [
        (0.0, "现状诊断", 15.0, D.C["warn"], "bold", 0.020),
        (0.0, p["problem"], 9.6, D.C["ink"], "normal", 0.028),
        (0.0, "站域口径：实测等时圈", 11.5, D.C["ink"], "bold", 0.012),
        (0.0, "站域不是圆。以真实站位为原点、16 个方位各取实测步行路径，"
              "按 75 m/min 步行预算反算每个方位能走到的直线距离，连成实测可达"
              "边界。本站 5 分钟中位 %dm（%d-%dm）、10 分钟中位 %dm（%d-%dm）、"
              "15 分钟中位 %dm（%d-%dm）。方位间差异即切割的直接后果：同一时间"
              "预算下，通畅方向与被切断方向可差数倍。数据源为高德步行路径规划"
              "（2026-08-09 实测），仍须以现场步行网络、过街延误与无障碍条件校核。"
              % (rng[5] + rng[10] + rng[15]),
         8.8, D.C["mute"], "normal", 0.024),
        (0.0, "切割诊断：立体 %d 段 / 平面 %d 段" % (len(cut), len(arter)),
         11.5, D.C["warn"], "bold", 0.012),
        (0.0, "实线为 OSM motorway 与 trunk 等级道路，属立体切割，只能靠桥隧"
              "过街，是步行可达的硬断点。虚线为 primary 等级主干路，属平面切割，"
              "可过街但受信号周期与路口宽度影响。凡被切割线穿过的圈层为名义"
              "可达、实际须绕行或等待，须以实测步行网络与过街点位切除后重算。",
         8.8, D.C["mute"], "normal", 0.024),
        (0.0, "待实测", 11.5, D.C["mute"], "bold", 0.012),
        (0.0, "\n".join("· " + t for t in p["survey"]), 8.8, D.C["mute"],
         "normal", 0.0),
    ], 0.985, 0.02)

    c2 = column(1)
    D.fit_blocks(c2, [
        (0.0, "5 分钟核心 · 中位%dm" % r5, 15.0, D.C["rail"], "bold", 0.018),
        (0.0, "\n".join("· " + t for t in p["fivemin"]), 9.6, D.C["ink"],
         "normal", 0.030),
        (0.0, "10 分钟圈 · 中位%dm" % r10, 15.0, D.C["rail"], "bold", 0.018),
        (0.0, "\n".join("· " + t for t in p["tenmin"]), 9.6, D.C["ink"],
         "normal", 0.030),
        (0.0, "15 分钟圈 · 中位%dm" % r15v, 11.5, D.C["mute"], "bold", 0.012),
        (0.0, "以既有社区更新为主，不以拆迁换取形式整齐；补齐普通就业、"
              "教育医疗与公交接驳，保留小商户与可承受租金。",
         8.8, D.C["mute"], "normal", 0.024),
        (0.0, "密度与混合梯度", 11.5, D.C["ink"], "bold", 0.012),
        (0.0, "出入口周边最高、向外递减，功能混合度随距离下降。此处只给相对"
              "关系：官方控规与精确边界未发布，容积率与建筑高度保持 unknown，"
              "本图不给具体数值。", 8.8, D.C["mute"], "normal", 0.0),
    ], 0.985, 0.02)

    c3 = column(2)
    blocks = [
        (0.0, "近期动作", 15.0, D.C["park"], "bold", 0.016),
        (0.0, "不依赖大拆建、可先行、可回退：", 8.8, D.C["mute"], "normal",
         0.020),
    ]
    for i, mv in enumerate(p["moves"], start=1):
        blocks.append((0.0, "%d. %s" % (i, mv), 9.8, D.C["ink"], "normal",
                       0.020))
    blocks += [
        (0.0, "站城一体", 11.5, D.C["ink"], "bold", 0.012),
        (0.0, "出入口、公交站台、非机动车停放、人行系统与建筑首层应在同一标高"
              "连续贯通，避免出闸后再上下天桥；非机动车在出入口 50m 内集中"
              "停放并清理占道。", 8.8, D.C["mute"], "normal", 0.024),
        (0.0, "本图性质", 11.5, D.C["warn"], "bold", 0.012),
        (0.0, "概念设计建议，非法定规划成果。站位为 OpenStreetMap provisional "
              "数据，实测出入口替换后须复算站域与步行圈；边界为仓库 provisional "
              "数据，非官方红线。", 8.6, D.C["mute"], "normal", 0.0),
    ]
    D.fit_blocks(c3, blocks, 0.985, 0.02)

    pdf.savefig(fig)
    fig.clf()


# ---------------------------------------------------------------- plate 9
def plate9(pdf, total):
    fig, pw, ph = D.new_page(PAGE)
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "重点区域站城原型与分期 · 数据校核",
        "三处重点区的站城原型、近中远期分期，以及大钟寺重点区 polygon 与真实站位的偏差校核",
        "L-%02d" % total, "L-%02d" % total)

    # --- sheet layout, millimetres from the bottom-left ---------------------
    bw = pw - 2 * m - 16
    x0 = m + 8
    body_top = ph - m - 52
    body_bot = m + 26
    gx = 14
    gy = 26
    # three key-area panels on top, discrepancy + phasing below, no dead band
    ah = (body_top - body_bot - gy) * 0.50
    dh = (body_top - body_bot - gy) - ah
    py = body_top - ah
    n = 3
    aw = (bw - (n - 1) * gx) / n
    order = ["PROV-KEY-001", "PROV-KEY-002", "PROV-KEY-003"]
    for i, k in enumerate(order):
        g = KEYS[k]
        px = x0 + i * (aw + gx)
        ax = D.ax_at(fig, px, py, aw, ah, PAGE)
        D.clean(ax)
        # fit to the panel aspect, else the three panels come out at three
        # different scales and read as unrelated drawings
        ext = D.fit_extent(pad_extent(g, 0.42), aw, ah)
        D.draw_base(ax, roads, heavy, metro, green, water, rivers, ext,
                    show_tertiary=True, lw_scale=1.2)
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color=D.C["life"], alpha=0.14, ec="none", zorder=2)
        ax.plot(xs, ys, color=D.C["life"], lw=1.8 * D.SCALE, zorder=7)
        lp = D.LabelPlacer(ax)
        inside = [s for s in stations if g.buffer(900).contains(s["pt"])]
        for s in inside:
            station_dot(ax, s, 8.0, core=(s["scope_level"] == "overall_design_area"))
        for s in inside:
            design = s["scope_level"] == "overall_design_area"
            lp.place(s["x"], s["y"], s["name_zh"], size=7.8,
                     weight="bold" if design else "normal",
                     color=D.C["ink"] if design else D.C["mute"], force=True)
        for s in inside:
            if s["scope_level"] == "overall_design_area":
                for mins, alpha in ((10, 0.10), (5, 0.16)):
                    ring, r = B.walk_ring(s, mins)
                    xs2, ys2 = ring.exterior.xy
                    ax.fill(xs2, ys2, color=D.C["rail"], alpha=alpha, ec="none", zorder=8)
        ax.set_title(B.KEY_LABELS[k], fontproperties=D.font(11.5, "bold"),
                     color=D.C["life"], pad=8)
        D.scale_bar(ax, 500, "500m", loc=(0.07, 0.05))
        area_ha = g.area / 1e4
        ax.text(0.985, 0.975, "复算面积 %.1f ha" % area_ha, transform=ax.transAxes,
                ha="right", va="top", fontproperties=D.font(7.6), color=D.C["mute"],
                zorder=70)

    # 大钟寺 discrepancy panel
    dw = bw * 0.46
    dy = body_bot
    axd = D.ax_at(fig, x0, dy, dw, dh, PAGE)
    D.clean(axd)
    kd = KEYS["PROV-KEY-003"]
    dzs = [s for s in stations if s["name_zh"] == "大钟寺"][0]
    bjb = [s for s in stations if s["name_zh"] == "北京北"][0]
    focus = kd.union(dzs["pt"].buffer(500)).union(bjb["pt"].buffer(400))
    ext = D.fit_extent(pad_extent(focus, 0.25), dw, dh)
    D.draw_base(axd, roads, heavy, metro, green, water, rivers, ext,
                show_tertiary=True, lw_scale=1.3)
    xs, ys = kd.exterior.xy
    axd.fill(xs, ys, color=D.C["life"], alpha=0.14, ec="none", zorder=2)
    axd.plot(xs, ys, color=D.C["life"], lw=1.8 * D.SCALE, zorder=7)
    lp = D.LabelPlacer(axd)
    for s in (dzs, bjb):
        station_dot(axd, s, 9.0, core=True)
    axd.annotate("", xy=(dzs["x"], dzs["y"]), xytext=(kd.centroid.x, kd.centroid.y),
                 arrowprops=dict(arrowstyle="<->", color=D.C["warn"], lw=1.8 * D.SCALE,
                                 mutation_scale=10 * D.SCALE,
                                 shrinkA=3, shrinkB=3), zorder=30)
    dist_m = dzs["pt"].distance(kd.centroid)
    # Two distances, because one alone is misleading: the arrow measures to the
    # polygon centroid, but the nearest edge is what a reviewer checks against.
    edge_m = dzs["pt"].distance(kd)
    mid_x = (dzs["x"] + kd.centroid.x) / 2
    mid_y = (dzs["y"] + kd.centroid.y) / 2
    # order matters: the two station names are the point of the panel, so they
    # claim their boxes before the centroid annotation, which is free to move
    lp.place(dzs["x"], dzs["y"], "大钟寺站（真实站位，13号线）", size=8.6, weight="bold")
    lp.place(bjb["x"], bjb["y"], "北京北站（S5，市郊铁路）", size=8.6, weight="bold")
    lp.place(mid_x, mid_y, "站位至形心 %.0fm" % dist_m, size=9.5, weight="bold",
             color=D.C["warn"])
    lp.place(kd.centroid.x, kd.centroid.y, "PROV-KEY-003 形心\n（仓库标注为大钟寺重点区）",
             size=8.0, color=D.C["life"])
    D.scale_bar(axd, 500, "500m", loc=(0.07, 0.05))
    axd.set_title("数据校核：大钟寺重点区 polygon 与真实站位偏差",
                  fontproperties=D.font(11.0, "bold"), color=D.C["warn"], pad=8)

    # phasing + metrics text, in two columns so it cannot run into the footer
    tw = bw - dw - 18
    ph_items = [
        ("近期（可先行、低成本、可回退）", D.C["park"], [
            "站口 200m 内连续步道、雨棚、照明与无障碍改造（7站同步）",
            "平交口行人相位优先与过街加密，先做学院路、西直门外大街",
            "非机动车停放正规化，清理站口占道",
            "统一导视：北京北—西直门换乘通道优先",
        ]),
        ("中期（需专项论证）", D.C["life"], [
            "跨京藏高速、跨铁路慢行connector（学知园、六道口）",
            "学院桥立交桥下空间改造为步行连廊与公共活动场",
            "园区与校园围墙开口，站到园/站到校直连",
            "10分钟圈补齐社区医疗、托育、学校与运动设施",
        ]),
        ("远期（需控规与权属落实）", D.C["rail"], [
            "站城复合核心的功能混合与租赁住房供给",
            "京张遗址公园主入口与遗产门厅（北京北）",
            "径向绿廊穿透，形成连通而非封闭的绿环",
            "既有社区以更新为主，保留小商户与可承受租金",
        ]),
    ]
    open_items = [
        ("尚未解决 / 需业主与官方数据决定", D.C["warn"], [
            "范围口径已定：按官方四至（业主 2026-08-08 确认），上地、清河、"
            "西二旗不出逐站详图",
            "PROV-KEY-003 大钟寺 polygon 形心距真实站位 %.0fm（最近边界 %.0fm），"
            "须以官方重点区边界复核" % (dist_m, edge_m),
            "官方红线、控规指标、道路红线、权属、文保控制线均未发布",
            "站位为 OpenStreetMap provisional 数据，实测出入口发布后 9 张图板须整体复算",
        ]),
    ]

    # split across two columns: near+mid on the left, far+open on the right,
    # each fitted so the block can never cross the footer rule
    groups = [ph_items[:2], ph_items[2:] + open_items]
    tgap = 14
    tcw = (tw - tgap) / 2
    for ci, grp in enumerate(groups):
        tx = D.ax_at(fig, x0 + dw + 18 + ci * (tcw + tgap), dy, tcw, dh, PAGE)
        D.clean(tx, frame=False)
        tx.set_xlim(0, 1)
        tx.set_ylim(0, 1)
        blocks = []
        if ci == 0:
            blocks.append((0.0, "分期与实施顺序", 12.5, D.C["ink"], "bold",
                           0.018))
        for title, col, items in grp:
            blocks.append((0.0, title, 9.6, col, "bold", 0.012))
            for it in items:
                blocks.append((0.02, "· " + it, 7.6, D.C["ink"], "normal",
                               0.006))
            blocks.append((0.0, "", 1.0, D.C["ink"], "normal", 0.010))
        D.fit_blocks(tx, blocks, 0.985, 0.02)

    pdf.savefig(fig)
    fig.clf()


def main():
    path = os.path.join(OUT, "a0-boards.pdf")
    total = 2 + len(DESIGN)  # L-01 overview + one per station + L-09 key areas
    with PdfPages(path) as pdf:
        plate1(pdf, total)
        for i, s in enumerate(DESIGN, start=2):
            plate_station(pdf, s, i, total)
            print("  L-%02d %s" % (i, s["name_zh"]))
        plate9(pdf, total)
    print("wrote", path, "(%d plates)" % total)


if __name__ == "__main__":
    main()

"""Regenerate the five README/proposal figures from the real base map.

The figures shipped on 2026-08-07 were built on the same flawed method as the
old PDFs: TOD cores at key-area polygon centroids, concentric-circle walk
rings, no real station named, and the 5/10/15-minute labels written at one
shared baseline (visibly garbled in site-overview.png and key-areas.png).
The PDFs were rebuilt; these were not, so the README still showed the old
method. This regenerates all five from the same data path as make_a0/make_a3:
real OSM station coordinates, detour-adjusted radii, severance overlay.

Filenames are fixed by REQUIRED_PROPOSAL_IMAGE_PATHS in
scripts/validate_submission.py and must not change.
"""
import json
import os

import matplotlib
import basemap as B
import draw as D

# draw.py selects the pdf backend for the plates; these outputs are PNG.
matplotlib.use("agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from station_program import CORRIDOR_ROLE, PROGRAM  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "figures")
# Repo-relative: tools/ sits inside the repository, so a clone resolves the
# submission metrics without anyone editing an absolute home path first.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS = os.path.join(REPO, "submissions/lumixraku/rail-life-rings/metrics.json")

RINGS = [(5, "#c0392b"), (10, "#d98324"), (15, "#3f7d54")]


def new_fig(w_mm, h_mm):
    """Figure sized in mm, with draw.py's type scale set from the width."""
    D.SCALE = w_mm / 210.0
    fig = plt.figure(figsize=(w_mm * D.MM, h_mm * D.MM), dpi=190)
    fig.patch.set_facecolor(D.C["paper"])
    return fig


def head(fig, title, sub, tag=None):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0.0, 0.925), 1.0, 0.075, color=D.C["band"],
                           zorder=0, transform=ax.transAxes))
    ax.text(0.018, 0.972, title, fontproperties=D.font(11.5, "bold"),
            color=D.C["ink"], va="center", zorder=2)
    ax.text(0.018, 0.941, sub, fontproperties=D.font(6.4),
            color=D.C["mute"], va="center", zorder=2)
    if tag:
        ax.text(0.982, 0.962, tag, fontproperties=D.font(6.2),
                color=D.C["rail"], ha="right", va="center", zorder=2)
    return ax


def foot(ax, text):
    ax.text(0.018, 0.014, text, fontproperties=D.font(5.4),
            color=D.C["mute"], va="bottom", zorder=2)


def extent_of(geoms, pad=0.06):
    xs0 = min(g.bounds[0] for g in geoms)
    ys0 = min(g.bounds[1] for g in geoms)
    xs1 = max(g.bounds[2] for g in geoms)
    ys1 = max(g.bounds[3] for g in geoms)
    dx, dy = (xs1 - xs0) * pad, (ys1 - ys0) * pad
    return xs0 - dx, ys0 - dy, xs1 + dx, ys1 + dy


def fit_extent(ext, w, h):
    """Expand an extent to the axes aspect so circles stay circular."""
    minx, miny, maxx, maxy = ext
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    ew, eh = maxx - minx, maxy - miny
    if ew / eh < w / h:
        ew = eh * w / h
    else:
        eh = ew * h / w
    return cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2


def load_all():
    bnd = B.load_boundaries()
    roads = B.load_roads()
    heavy, metro = B.load_rail()
    return dict(
        bnd=bnd, roads=roads, heavy=heavy, metro=metro,
        green=B.load_polys("green"), water=B.load_polys("water"),
        rivers=B.load_water_lines(), stations=B.load_stations(),
        barriers=B.barrier_lines(roads),
    )


def draw_boundaries(ax, bnd, keys=True):
    for pid, style in (("PROV-RESEARCH-001", dict(ls=(0, (7, 5)), lw=1.1)),
                       ("PROV-SITE-001", dict(ls="-", lw=1.5))):
        g = bnd.get(pid)
        if g is None:
            continue
        xs, ys = g.exterior.xy
        ax.plot(xs, ys, color=D.C["ink"], zorder=8, **style)
    if not keys:
        return
    for pid in ("PROV-KEY-001", "PROV-KEY-002", "PROV-KEY-003"):
        g = bnd.get(pid)
        if g is None:
            continue
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color=D.C["life"], alpha=0.13, ec=D.C["life"],
                lw=1.1, zorder=7)


def station_dots(ax, stations, lp, label_all=True):
    """Design-area stations get priority for label space over corridor ones."""
    deep = [s for s in stations if s["design_depth"] == "per_station_detailed"]
    corr = [s for s in stations if s["design_depth"] != "per_station_detailed"]
    for s in deep:
        ax.plot([s["x"]], [s["y"]], "o", ms=5.2 * D.SCALE, mfc=D.C["rail"],
                mec="white", mew=1.1 * D.SCALE, zorder=30)
    for s in corr:
        ax.plot([s["x"]], [s["y"]], "o", ms=3.0 * D.SCALE, mfc="white",
                mec=D.C["rail"], mew=1.0 * D.SCALE, zorder=29)
    for s in deep:
        lp.place(s["x"], s["y"], s["name_zh"], size=6.4, weight="bold",
                 color=D.C["ink"])
    if label_all:
        for s in corr:
            lp.place(s["x"], s["y"], s["name_zh"], size=5.2,
                     color=D.C["mute"])


# --- figure 1: overall concept, evidence boundary, corridor -----------------
def fig_site_overview(d):
    fig = new_fig(300, 190)
    ax0 = head(fig, "京张轨道生活环 · 总体概念与证据边界",
               "官方四至范围内 21 座轨道站；7 站在总体设计范围内做逐站设计，14 站做廊道接驳",
               "图 1 / 5")
    # Corridor runs north-south (5.1km x 9.9km), so the map is a portrait
    # panel: a wide axes would pad sideways to keep scale isotropic.
    ax = fig.add_axes([0.035, 0.085, 0.40, 0.82])
    D.clean(ax)
    ext = fit_extent(extent_of([d["bnd"]["PROV-RESEARCH-001"]], pad=0.05),
                     0.40, 0.82)
    D.draw_base(ax, d["roads"], d["heavy"], d["metro"], d["green"],
                d["water"], d["rivers"], ext, lw_scale=0.55)
    draw_boundaries(ax, d["bnd"])
    lp = D.LabelPlacer(ax)
    station_dots(ax, d["stations"], lp)
    D.scale_bar(ax, 2000, "2km", loc=(0.06, 0.025))
    D.north_arrow(ax, loc=(0.90, 0.945))

    tx = fig.add_axes([0.475, 0.085, 0.505, 0.82])
    tx.set_axis_off()
    deep = [s for s in d["stations"]
            if s["design_depth"] == "per_station_detailed"]
    corr = [s for s in d["stations"]
            if s["design_depth"] != "per_station_detailed"]
    blocks = [
        (0.0, "一脊三核、三圈一滤环、多条缝合径", 7.6, D.C["ink"], "bold", 0.012),
        (0.0, "以京张铁路慢行主轴串联三处重点区，把通勤、就业、住房、医疗、"
              "教育、商业和公园组织成可步行的生活圈。公园做成“环而不隔”的绿色"
              "滤环，而不是封闭同心圆。", 5.9, D.C["mute"], "normal", 0.022),
        (0.0, "站点如何确定", 6.8, D.C["rail"], "bold", 0.010),
        (0.0, "对官方四至范围做点面判定，不再取重点区 polygon 的几何中心。"
              "TOD 核对应真实站点，站位来自 OpenStreetMap，待实测出入口替换。",
         5.9, D.C["mute"], "normal", 0.022),
        (0.0, "总体设计范围 11.4km²（%d 站，逐站设计）" % len(deep),
         6.6, D.C["ink"], "bold", 0.008),
        (0.0, "、".join(s["name_zh"] for s in deep), 5.9, D.C["ink"],
         "normal", 0.020),
        (0.0, "统筹研究范围 43.6km²（%d 站，廊道与接驳）" % len(corr),
         6.6, D.C["ink"], "bold", 0.008),
        (0.0, "、".join(s["name_zh"] for s in corr), 5.9, D.C["mute"],
         "normal", 0.022),
        (0.0, "范围外（按业主 2026-08-08 决定守官方四至，不做逐站设计）",
         6.6, D.C["warn"], "bold", 0.008),
        (0.0, "上地 2.5km、清河 3.3km、西二旗 4.6km，均在北五环以北。",
         5.9, D.C["mute"], "normal", 0.0),
    ]
    D.fit_blocks(tx, blocks, 0.985, 0.09)

    lg = [
        Line2D([], [], color=D.C["ink"], lw=1.5, label="总体设计范围"),
        Line2D([], [], color=D.C["ink"], lw=1.1, ls=(0, (7, 5)),
               label="统筹研究范围"),
        Line2D([], [], color=D.C["life"], lw=1.1, label="三处重点区"),
        Line2D([], [], marker="o", color="none", mfc=D.C["rail"], mec="white",
               ms=4.6, label="逐站设计站点"),
        Line2D([], [], marker="o", color="none", mfc="white", mec=D.C["rail"],
               ms=3.2, label="廊道接驳站点"),
        Line2D([], [], color=D.C["ink"], lw=1.5, label="京张既有铁路"),
    ]
    ax.legend(handles=lg, loc="upper left", prop=D.font(4.4),
              framealpha=0.94, edgecolor=D.C["hair"], borderpad=0.5,
              handlelength=1.4, labelspacing=0.32)
    foot(ax0, "概念方案，非法定规划成果。边界为仓库 provisional 数据，"
              "站位来自 OpenStreetMap；官方红线与实测出入口发布后须整体复算。")
    fig.savefig(os.path.join(OUT, "site-overview.png"),
                facecolor=fig.get_facecolor())
    plt.close(fig)


# --- figure 2: walk rings and three-level scope -----------------------------
def fig_land_use(d):
    fig = new_fig(300, 190)
    ax0 = head(fig, "5 / 10 / 15 分钟圈与三层范围传导",
               "半径按 分钟 × 75m/min ÷ 1.35 绕行系数换算，从真实站位起算，"
               "并叠加高速与主干路切割线", "图 2 / 5")
    # The design area is a 1.4km x 9.7km strip (1:7). A wide axes would have to
    # expand the view sideways to keep circles round, leaving the sheet mostly
    # empty -- so the map is a portrait strip and the freed width carries the
    # per-station ring table.
    ax = fig.add_axes([0.035, 0.085, 0.235, 0.82])
    D.clean(ax)
    deep = [s for s in d["stations"]
            if s["design_depth"] == "per_station_detailed"]
    ext = fit_extent(extent_of([d["bnd"]["PROV-SITE-001"]], pad=0.06),
                     0.235, 0.82)
    D.draw_base(ax, d["roads"], d["heavy"], d["metro"], d["green"],
                d["water"], d["rivers"], ext, show_tertiary=True, lw_scale=0.7)
    draw_boundaries(ax, d["bnd"])
    for mins, col in reversed(RINGS):
        for s in deep:
            ring, _ = B.walk_ring(s, mins)
            xs, ys = ring.exterior.xy
            ax.fill(xs, ys, color=col, alpha=0.17, ec=col, lw=1.1, zorder=10)
    # severance: the reason a nominal radius overstates reach
    for ln in d["barriers"]:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=1.5 * D.SCALE, alpha=0.75,
                zorder=12)
    lp = D.LabelPlacer(ax)
    station_dots(ax, deep, lp)
    D.scale_bar(ax, 1000, "1km", loc=(0.06, 0.025))
    D.north_arrow(ax, loc=(0.87, 0.94))

    # per-station ring table: the strip map cannot carry seven stations' worth
    # of programme text, so the freed width states it station by station.
    mx = fig.add_axes([0.305, 0.085, 0.325, 0.82])
    mx.set_axis_off()
    mx.set_xlim(0, 1)
    mx.set_ylim(0, 1)
    mx.text(0.0, 0.985, "逐站 5 / 10 分钟内容",
            fontproperties=D.font(7.4, "bold"), color=D.C["ink"], va="top")
    y = 0.925
    dy = 0.925 / (len(deep) + 0.5)
    for i, s in enumerate(deep):
        pg = PROGRAM[s["name_zh"]]
        if i % 2 == 0:
            mx.add_patch(Rectangle((0.0, y - dy * 0.94), 1.0, dy * 0.90,
                                   color=D.C["band"], ec="none", zorder=0))
        mx.text(0.015, y - dy * 0.16, s["name_zh"],
                fontproperties=D.font(6.4, "bold"), color=D.C["rail"],
                va="center")
        mx.text(0.30, y - dy * 0.16, pg["role"],
                fontproperties=D.font(5.2), color=D.C["mute"], va="center")
        mx.text(0.015, y - dy * 0.46, "5 分钟",
                fontproperties=D.font(5.2, "bold"), color=RINGS[0][1],
                va="center")
        mx.text(0.16, y - dy * 0.46, "、".join(pg["fivemin"][:3]),
                fontproperties=D.font(5.2), color=D.C["ink"], va="center")
        mx.text(0.015, y - dy * 0.74, "10 分钟",
                fontproperties=D.font(5.2, "bold"), color=RINGS[1][1],
                va="center")
        mx.text(0.16, y - dy * 0.74, "、".join(pg["tenmin"][:3]),
                fontproperties=D.font(5.2), color=D.C["ink"], va="center")
        y -= dy

    tx = fig.add_axes([0.665, 0.085, 0.315, 0.82])
    tx.set_axis_off()
    blocks = [
        (0.0, "三圈：按时间分配内容，不按图上直线半径", 7.4, D.C["ink"], "bold", 0.014),
    ]
    for mins, _ in RINGS:
        r = mins * 75.0 / 1.35
        name = {5: "站城复合核心", 10: "全龄生活混合圈",
                15: "普通居住与社区圈"}[mins]
        blocks.append((0.0, "%d 分钟 · %s · 半径 %dm" % (mins, name, round(r)),
                       6.4, D.C["ink"], "bold", 0.006))
        blocks.append((0.0, {
            5: "通勤接驳、早餐与夜间餐饮、便民服务、非机动车停放、轮班休息。",
            10: "租赁住房、社区医疗与托育、学校、日常商业、运动与公园入口。",
            15: "既有社区更新、普通就业岗位、教育医疗补齐、公交与需求响应接驳。",
        }[mins], 5.8, D.C["mute"], "normal", 0.016))
    blocks += [
        (0.0, "为什么不是同心圆", 7.0, D.C["warn"], "bold", 0.010),
        (0.0, "直线半径会把“名义可达”当成“实际可达”。图上红线是高速与主干路，"
              "行人需绕到最近过街点，因此同一半径内的东西两侧步行时间可能相差一倍以上。"
              "缝合径优先解决这些断点。", 5.8, D.C["mute"], "normal", 0.020),
        (0.0, "三层范围传导", 7.0, D.C["rail"], "bold", 0.010),
        (0.0, "统筹研究范围 43.6km²：廊道结构、轨道接驳与跨区关系。\n"
              "总体设计范围 11.4km²：逐站设计深度，7 站全覆盖。\n"
              "重点区（3 处）：详细设计与项目抓手。", 5.8, D.C["mute"],
         "normal", 0.016),
        (0.0, "面积为 provisional 边界复算值，只用于方案内部比较，不是法定指标。",
         5.4, D.C["warn"], "normal", 0.0),
    ]
    D.fit_blocks(tx, blocks, 0.985, 0.06)

    lg = [Line2D([], [], color=c, lw=1.0, label="%d 分钟（%dm）"
                 % (m, round(m * 75.0 / 1.35))) for m, c in RINGS]
    lg.append(Line2D([], [], color=D.C["warn"], lw=1.5, label="切割线"))
    ax.legend(handles=lg, loc="upper left", prop=D.font(4.6),
              framealpha=0.94, edgecolor=D.C["hair"], borderpad=0.5,
              handlelength=1.4, labelspacing=0.35)
    foot(ax0, "步行圈为启发式换算，非实测等时圈；须以真实步行路网与站点出入口复算。")
    fig.savefig(os.path.join(OUT, "land-use-structure.png"),
                facecolor=fig.get_facecolor())
    plt.close(fig)


# --- figure 3: three key areas, one panel each ------------------------------
KEY_PANELS = [
    ("PROV-KEY-001", "众智园AI自主创新加速区", "可负担通勤与测试站城", ["学知园"]),
    ("PROV-KEY-002", "北京AI原点社区", "职住学共享站城", ["学院桥", "六道口", "西土城"]),
    ("PROV-KEY-003", "大钟寺AI产业聚集区", "全时生活与普通就业站城", ["北京北", "西直门"]),
]


def fig_key_areas(d):
    fig = new_fig(300, 205)
    ax0 = head(fig, "三处重点区的 TOD 原型与项目抓手",
               "每处重点区对应真实站点与各自的切割问题，原型不通用；"
               "近期动作来自逐站设计", "图 3 / 5")
    by_name = {s["name_zh"]: s for s in d["stations"]}
    for i, (pid, title, proto, names) in enumerate(KEY_PANELS):
        x = 0.035 + i * 0.322
        ax = fig.add_axes([x, 0.455, 0.295, 0.40])
        D.clean(ax)
        here = [by_name[n] for n in names if n in by_name]
        geoms = [d["bnd"][pid]] + [
            B.walk_ring(s, 15)[0] for s in here]
        ext = fit_extent(extent_of(geoms, pad=0.16), 0.295, 0.40)
        D.draw_base(ax, d["roads"], d["heavy"], d["metro"], d["green"],
                    d["water"], d["rivers"], ext, show_tertiary=True,
                    lw_scale=1.0)
        g = d["bnd"][pid]
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color=D.C["life"], alpha=0.13, ec=D.C["life"],
                lw=1.3, zorder=7)
        for mins, col in reversed(RINGS):
            for s in here:
                ring, _ = B.walk_ring(s, mins)
                rx, ry = ring.exterior.xy
                ax.fill(rx, ry, color=col, alpha=0.085, ec=col, lw=0.9,
                        zorder=10)
        for ln in d["barriers"]:
            rx, ry = ln.xy
            ax.plot(rx, ry, color=D.C["warn"], lw=1.6 * D.SCALE, alpha=0.75,
                    zorder=12)
        lp = D.LabelPlacer(ax)
        for s in here:
            ax.plot([s["x"]], [s["y"]], "o", ms=6.0 * D.SCALE,
                    mfc=D.C["rail"], mec="white", mew=1.2 * D.SCALE, zorder=30)
            lp.place(s["x"], s["y"], s["name_zh"], size=7.0, weight="bold")
        D.scale_bar(ax, 500, "500m")
        # Title sits inside the panel: as an axes title it collided with the
        # header subtitle on the first column.
        ax.text(0.5, 1.055, title, fontproperties=D.font(6.6, "bold"),
                color=D.C["ink"], ha="center", va="bottom",
                transform=ax.transAxes)
        ax.text(0.5, 1.012, proto, fontproperties=D.font(5.6),
                color=D.C["mute"], ha="center", va="bottom",
                transform=ax.transAxes)

        tx = fig.add_axes([x, 0.055, 0.295, 0.395])
        tx.set_axis_off()
        lead = names[0]
        pg = PROGRAM[lead]
        blocks = [
            (0.0, "主站：%s" % lead, 6.4, D.C["rail"], "bold", 0.006),
            (0.0, pg["role"], 5.6, D.C["mute"], "normal", 0.016),
            (0.0, "现状问题", 6.2, D.C["warn"], "bold", 0.005),
            (0.0, pg["problem"], 5.6, D.C["ink"], "normal", 0.016),
            (0.0, "5 分钟核心", 6.2, D.C["ink"], "bold", 0.005),
            (0.0, "、".join(pg["fivemin"]), 5.6, D.C["mute"], "normal", 0.014),
            (0.0, "10 分钟生活圈", 6.2, D.C["ink"], "bold", 0.005),
            (0.0, "、".join(pg["tenmin"]), 5.6, D.C["mute"], "normal", 0.014),
            (0.0, "近期项目抓手", 6.2, D.C["park"], "bold", 0.005),
            (0.0, "\n".join("· " + m for m in pg["moves"]), 5.6, D.C["ink"],
             "normal", 0.014),
            (0.0, "前置调研", 6.2, D.C["mute"], "bold", 0.005),
            (0.0, "、".join(pg["survey"]), 5.4, D.C["mute"], "normal", 0.0),
        ]
        if len(names) > 1:
            blocks.insert(2, (0.0, "同区其他站：%s" % "、".join(names[1:]),
                              5.6, D.C["mute"], "normal", 0.014))
        D.fit_blocks(tx, blocks, 0.985, 0.02)
    foot(ax0, "重点区几何为 provisional，非官方红线。PROV-KEY-003 的 polygon "
              "与真实大钟寺站相距约 1.7km，图中以站点为准，仓库几何未擅改。")
    fig.savefig(os.path.join(OUT, "key-areas.png"),
                facecolor=fig.get_facecolor())
    plt.close(fig)


# --- figure 4: mobility and penetrating blue-green --------------------------
def fig_mobility(d):
    fig = new_fig(300, 190)
    ax0 = head(fig, "交通、轨道与穿透式蓝绿系统",
               "道路分级、轨道线路、蓝绿网络与切割点叠合；绿环“环而不隔”，"
               "径向通道优先", "图 4 / 5")
    # Research area is 5.1km x 9.9km, so a wide axes would pad sideways and
    # leave the sheet empty. Portrait map, freed width carries the corridor
    # interchange roles.
    ax = fig.add_axes([0.035, 0.085, 0.30, 0.82])
    D.clean(ax)
    ext = fit_extent(extent_of([d["bnd"]["PROV-RESEARCH-001"]], pad=0.05),
                     0.30, 0.82)
    D.draw_base(ax, d["roads"], d["heavy"], d["metro"], d["green"],
                d["water"], d["rivers"], ext, show_tertiary=True, lw_scale=0.6)
    draw_boundaries(ax, d["bnd"], keys=False)
    for ln in d["barriers"]:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=1.3 * D.SCALE, alpha=0.7,
                zorder=12)
    lp = D.LabelPlacer(ax)
    station_dots(ax, d["stations"], lp, label_all=False)
    D.scale_bar(ax, 2000, "2km", loc=(0.06, 0.025))
    D.north_arrow(ax, loc=(0.88, 0.945))

    # corridor stations: their interchange role is the content the old figure
    # left out entirely
    cx = fig.add_axes([0.365, 0.085, 0.285, 0.82])
    cx.set_axis_off()
    cx.set_xlim(0, 1)
    cx.set_ylim(0, 1)
    cx.text(0.0, 0.985, "廊道接驳站点角色（%d 站）" % len(CORRIDOR_ROLE),
            fontproperties=D.font(7.0, "bold"), color=D.C["ink"], va="top")
    y = 0.930
    dy = 0.930 / (len(CORRIDOR_ROLE) + 0.6)
    for i, (name, role) in enumerate(CORRIDOR_ROLE.items()):
        if i % 2 == 0:
            cx.add_patch(Rectangle((0.0, y - dy * 0.92), 1.0, dy * 0.88,
                                   color=D.C["band"], ec="none", zorder=0))
        cx.text(0.015, y - dy * 0.44, name,
                fontproperties=D.font(5.6, "bold"), color=D.C["rail"],
                va="center")
        for j, ln in enumerate(D.wrap_cjk(role, 26)[:2]):
            cx.text(0.30, y - dy * (0.26 + j * 0.42), ln,
                    fontproperties=D.font(5.0), color=D.C["mute"], va="center")
        y -= dy

    tx = fig.add_axes([0.685, 0.085, 0.295, 0.82])
    tx.set_axis_off()
    nrail = len(d["heavy"]) + len(d["metro"])
    nroad = sum(len(v) for v in d["roads"].values())
    blocks = [
        (0.0, "交通优先级", 7.4, D.C["ink"], "bold", 0.010),
        (0.0, "步行与无障碍 → 骑行 → 公交与需求响应接驳 → 轨道换乘 → "
              "必要机动车。", 5.9, D.C["mute"], "normal", 0.020),
        (0.0, "近期不依赖大拆建的动作", 6.8, D.C["park"], "bold", 0.008),
        (0.0, "站口导视、遮雨、座椅、厕所、非机动车停车、公交时刻协同、"
              "路口安全、夜间照明。", 5.9, D.C["mute"], "normal", 0.020),
        (0.0, "切割点是首要问题", 6.8, D.C["warn"], "bold", 0.008),
        (0.0, "红线为高速与主干路。京藏高速与北五环在北段形成双重切割，"
              "学院路与立交在中段夹持站口，西直门外大街与立交切断南段站域。"
              "缝合径优先加密过街，而不是先做形象建筑。", 5.9, D.C["mute"],
         "normal", 0.020),
        (0.0, "环而不隔的绿色滤环", 6.8, D.C["park"], "bold", 0.008),
        (0.0, "连续绿地不应成为普通社区与就业、学校、医院之间的新障碍。"
              "每个核心都需要清晰、明亮、无障碍的径向入口，"
              "绿廊与水系穿透而非圈占站点价值。", 5.9, D.C["mute"], "normal",
         0.020),
        (0.0, "分期与前置条件", 6.8, D.C["ink"], "bold", 0.008),
        (0.0, "0–12 个月：三站步行审计、导视与遮雨、路口安全、夜行照明、"
              "公众共创台。前置为交通与权属许可。\n"
              "1–3 年：首层共享服务、公交协同、普通租赁住房试点、"
              "社区医疗教育补缺、绿环径向通道。前置为控规、消防与住房政策。\n"
              "3 年以上：站城复合更新、跨线缝合、完整绿网与多站运营平台。"
              "前置为官方边界、工程资金与审批。", 5.6, D.C["mute"],
         "normal", 0.018),
        (0.0, "底图数据", 6.8, D.C["rail"], "bold", 0.008),
        (0.0, "%d 条分级道路、%d 条轨道线段，以及绿地与水系图层，"
              "均来自 OpenStreetMap。切割线为 motorway 与 trunk 共 %d 段。"
              % (nroad, nrail, len(d["barriers"])), 5.6, D.C["mute"],
         "normal", 0.0),
    ]
    D.fit_blocks(tx, blocks, 0.985, 0.05)

    lg = [Line2D([], [], color=B.ROAD_STYLE[c]["color"],
                 lw=B.ROAD_STYLE[c]["lw"], label=n)
          for c, n in (("motorway", "高速"), ("trunk", "快速/主干"),
                       ("primary", "主要道路"), ("secondary", "次要道路"))]
    lg += [
        Line2D([], [], color=D.C["warn"], lw=1.4, label="切割线（高速/主干）"),
        Line2D([], [], color=D.C["ink"], lw=1.5, label="京张既有铁路"),
        Line2D([], [], color=D.C["rail"], lw=0.9, alpha=0.6, label="轨道交通"),
        Line2D([], [], color="#bcd3e3", lw=1.6, label="河道"),
    ]
    ax.legend(handles=lg, loc="upper left", prop=D.font(4.4),
              framealpha=0.94, edgecolor=D.C["hair"], borderpad=0.5,
              handlelength=1.4, labelspacing=0.32)
    foot(ax0, "概念建议，非交通工程结论；过街与路权改善须以实测流量与"
              "交管、权属许可为前提。")
    fig.savefig(os.path.join(OUT, "mobility-bluegreen.png"),
                facecolor=fig.get_facecolor())
    plt.close(fig)


# --- figure 5: metrics, coverage and data gaps ------------------------------
ZH = {
    "site_area_sqm": "总体设计范围面积",
    "building_footprint_area_sqm": "建筑基底面积",
    "green_ratio": "绿地比例",
    "public_space_ratio": "公共空间比例",
    "floor_area_ratio": "容积率",
    "key_area_count": "重点区数量",
    "tod_node_count": "TOD 节点数量",
    "scenario_card_count": "场景卡数量",
}


def fmt_val(k, m):
    v = m.get("value")
    if v is None:
        return "待官方数据"
    if m.get("unit") == "ratio":
        return "%.1f%%" % (v * 100)
    if m.get("unit") == "sqm":
        return "%.2f km²" % (v / 1e6) if v > 1e5 else "%.2f 万 m²" % (v / 1e4)
    return "%g" % v


def fig_metrics(d):
    met = json.load(open(METRICS))["metrics"]
    fig = new_fig(300, 175)
    ax0 = head(fig, "核心指标、任务覆盖与待补数据",
               "指标为方案图层复算值，只用于方案内部比较与拓扑检查，不是法定指标",
               "图 5 / 5")

    # metric table
    ax = fig.add_axes([0.035, 0.085, 0.40, 0.80])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0, 0.985, "指标复算", fontproperties=D.font(7.4, "bold"),
            color=D.C["ink"], va="top")
    rows = list(met.items())
    y = 0.915
    dy = 0.915 / (len(rows) + 1.6)
    for k, m in rows:
        known = m.get("status") == "known"
        ax.add_patch(Rectangle((0.0, y - dy * 0.80), 1.0, dy * 0.74,
                               color=D.C["band"] if known else "#fdf1ee",
                               ec="none", zorder=0))
        ax.text(0.018, y - dy * 0.30, ZH.get(k, k),
                fontproperties=D.font(5.9, "bold"),
                color=D.C["ink"] if known else D.C["warn"], va="center")
        ax.text(0.66, y - dy * 0.30, fmt_val(k, m),
                fontproperties=D.font(5.9), color=D.C["ink"], va="center")
        ax.text(0.985, y - dy * 0.30,
                {"high": "高", "medium": "中", "low": "低"}.get(
                    m.get("confidence"), "—"),
                fontproperties=D.font(5.2), color=D.C["mute"],
                ha="right", va="center")
        y -= dy
    ax.text(0.0, y - dy * 0.1, "右列为置信度。容积率无官方控规与精确边界，不予给出。",
            fontproperties=D.font(5.2), color=D.C["mute"], va="top")

    # ratio bars
    bx = fig.add_axes([0.475, 0.535, 0.225, 0.34])
    D.clean(bx, frame=False)
    names, vals = [], []
    for k in ("green_ratio", "public_space_ratio"):
        names.append(ZH[k])
        vals.append(met[k]["value"] * 100)
    bx.barh(range(len(vals)), vals, color=[D.C["park"], D.C["rail"]],
            height=0.42, zorder=3)
    bx.set_yticks(range(len(vals)))
    bx.set_yticklabels(names, fontproperties=D.font(5.8))
    bx.set_xlim(0, max(vals) * 1.45)
    bx.invert_yaxis()
    for i, v in enumerate(vals):
        bx.text(v + max(vals) * 0.04, i, "%.1f%%" % v,
                fontproperties=D.font(5.8, "bold"), va="center",
                color=D.C["ink"])
    bx.set_title("范围内比例复算", fontproperties=D.font(6.6, "bold"),
                 color=D.C["ink"], loc="left", pad=3 * D.SCALE)

    # station coverage
    cx = fig.add_axes([0.475, 0.085, 0.225, 0.335])
    D.clean(cx, frame=False)
    deep = sum(1 for s in d["stations"]
               if s["design_depth"] == "per_station_detailed")
    corr = len(d["stations"]) - deep
    cx.bar([0, 1], [deep, corr], color=[D.C["rail"], "#aab4c0"],
           width=0.46, zorder=3)
    cx.set_xticks([0, 1])
    cx.set_xticklabels(["逐站设计\n（设计范围内）", "廊道接驳\n（研究范围内）"],
                       fontproperties=D.font(5.6))
    cx.set_ylim(0, max(deep, corr) * 1.35)
    for i, v in enumerate([deep, corr]):
        cx.text(i, v + max(deep, corr) * 0.05, "%d 站" % v,
                fontproperties=D.font(6.2, "bold"), ha="center",
                color=D.C["ink"])
    cx.set_title("站点覆盖 · 共 %d 站" % len(d["stations"]),
                 fontproperties=D.font(6.6, "bold"), color=D.C["ink"],
                 loc="left", pad=3 * D.SCALE)

    # gaps
    tx = fig.add_axes([0.735, 0.085, 0.245, 0.80])
    tx.set_axis_off()
    blocks = [
        (0.0, "待补数据（发布后须整体复算）", 7.0, D.C["warn"], "bold", 0.012),
        (0.0, "· 官方精确总体与重点区边界\n· 站点出入口实测位置\n"
              "· 控规指标与容积率\n· 道路红线与权属\n· 市政、消防与文保控制线\n"
              "· 真实步行路网等时圈\n· 站厅客流与过街延误实测",
         5.8, D.C["mute"], "normal", 0.022),
        (0.0, "已知数据偏差", 6.8, D.C["warn"], "bold", 0.008),
        (0.0, "PROV-KEY-003 标注为大钟寺，但 polygon 位于 lat 39.944–39.950，"
              "真实大钟寺站在 39.965，相距约 1.7km。图纸以真实站位为准并标注该偏差，"
              "仓库几何未擅改。", 5.7, D.C["ink"], "normal", 0.020),
        (0.0, "自检状态", 6.8, D.C["park"], "bold", 0.008),
        (0.0, "self_check_submission.py 通过，可进入正式评审；"
              "空间复核仅 3 条非阻断 KEY_AREA_PROVISIONAL 提示。",
         5.7, D.C["mute"], "normal", 0.018),
        (0.0, "站位来源", 6.8, D.C["rail"], "bold", 0.008),
        (0.0, "OpenStreetMap（DATA-SRC-OSM-STATIONS-20260808），"
              "状态为 provisional，待实测替换。", 5.7, D.C["mute"], "normal", 0.0),
    ]
    D.fit_blocks(tx, blocks, 0.985, 0.03)
    foot(ax0, "所有空间动作均为概念建议或供专业团队深化研究的参考方案，"
              "不含法定容积率、建筑高度、最终拆改留或政府建设承诺。")
    fig.savefig(os.path.join(OUT, "metrics-evidence.png"),
                facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = load_all()
    print("stations=%d roads=%d rail=%d barriers=%d" % (
        len(d["stations"]), sum(len(v) for v in d["roads"].values()),
        len(d["heavy"]) + len(d["metro"]), len(d["barriers"])))
    for fn in (fig_site_overview, fig_land_use, fig_key_areas,
               fig_mobility, fig_metrics):
        fn(d)
        print("ok", fn.__name__)
    for f in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, f)
        print("  %-28s %6.0f KB" % (f, os.path.getsize(p) / 1024))


if __name__ == "__main__":
    main()

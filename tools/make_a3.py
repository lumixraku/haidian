"""True-A3 booklet (297 x 420 mm portrait), vector, with a real text layer.

Deliberately NOT the A0 plates reshuffled — that was a defect in the previous
submission (4 of 9 embedded images were byte-identical across the two PDFs).
The booklet is a reading document: one spread per station, at a page scale where
a single station's 15-minute catchment fills the sheet.

p1     cover + scope + method
p2     corridor overview + the 21-station ledger
p3-9   one page per design-area station (7 pages)
p10    corridor-level stations (14)
p11    phasing + data caveats + the 大钟寺 discrepancy
"""
import math
import os

from matplotlib.backends.backend_pdf import PdfPages

import basemap as B
import draw as D
from station_program import CORRIDOR_ROLE, PROGRAM

PAGE = "A3"
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
TOTAL = 11


def pad_extent(geom, pad=0.10):
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    return (minx - w * pad, miny - h * pad, maxx + w * pad, maxy + h * pad)


def station_dot(ax, s, r_pt=5.0, core=False):
    col = D.C["rail"] if s["mode"] == "subway" else D.C["ink"]
    S = D.SCALE
    ax.plot([s["x"]], [s["y"]], marker="o", ms=r_pt * S, mfc="white", mec=col,
            mew=(1.6 if core else 1.1) * S, zorder=20)
    if core:
        ax.plot([s["x"]], [s["y"]], marker="o", ms=r_pt * 0.42 * S, mfc=col,
                mec="none", zorder=21)


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


# ------------------------------------------------------------------ p1 cover
def page_cover(pdf):
    fig, pw, ph = D.new_page(PAGE)
    ax, m, ts = D.sheet_frame(
        fig, PAGE, "京张轨道生活环",
        "面向普通人的全时 TOD 城市 · A3 方案图册",
        "01", "%02d" % TOTAL)

    tx = D.ax_at(fig, m + 6, m + 24, pw - 2 * m - 12, ph - 2 * m - 70, PAGE)
    D.clean(tx, frame=False)
    tx.set_xlim(0, 1); tx.set_ylim(0, 1)

    H, B_, W = D.C["ink"], D.C["ink"], D.C["warn"]
    M = D.C["mute"]
    blocks = [
        (0, "本册与图板的分工", 13, H, "bold", 0.008),
        (0, "A0 图板用于展陈，承载廊道结构与整体判断；本 A3 图册用于阅读与审校，"
            "按站逐页展开，每页页面比例正好容纳一座车站的 15 分钟步行 catchment。"
            "两者内容不重复：图册的逐站页含图板上放不下的功能配置与实测清单。",
         9.2, M, "normal", 0.020),
        (0, "三层范围", 13, H, "bold", 0.008),
        (0.015, "· 统筹研究范围 43.6 平方公里：区域岗位、住房、公共服务与轨道网络协同。",
         9.2, B_, "normal", 0.005),
        (0.015, "· 总体设计范围 11.4 平方公里：三组 TOD 生活圈、京张南北慢行脊、穿透式绿网。",
         9.2, B_, "normal", 0.005),
        (0.015, "· 重点区域 368.4 公顷：众智园、AI 原点社区、大钟寺三种站城原型。",
         9.2, B_, "normal", 0.020),
        (0, "站点分级与范围口径", 13, H, "bold", 0.008),
        (0, "对官方公告四至内的每座轨道站逐一做点面判定：7 座落在总体设计范围内，"
            "按逐站详细设计深度表达；14 座落在统筹研究范围内，按廊道与接驳层级表达。"
            "上地、清河、西二旗均在北五环以北、四至之外（距最近重点区分别约 2.5、3.3、4.6 公里），"
            "经业主 2026-08-08 确认按官方四至口径执行，不出逐站详图。",
         9.2, M, "normal", 0.020),
        (0, "等时圈算法：实测，不是圆", 13, H, "bold", 0.008),
        (0, "站位取真实站点坐标，不取重点区 polygon 形心。7 座逐站设计车站的站域"
            "为实测等时圈：每站 16 个方位、共 784 条高德步行路径（2026-08-09），"
            "按 75 米/分钟的步行预算反算每个方位实际能走到的直线距离，连成可达边界。",
         9.2, M, "normal", 0.012),
        (0, "此前版本用 半径 = 分钟 × 75 ÷ 1.35 画圆，两处都错了。实测绕行系数"
            "中位为 1.75 而非 1.35，故各圈一律画大：七站 15 分钟圈图面合计 1526 公顷，"
            "实测可达仅 961 公顷，虚报 37%。更要紧的是可达范围本不是圆——学知园"
            "5 分钟在通畅方位可达 284 米，跨京藏高速方位仅 38 米，相差 7 倍。"
            "圆同时高估被切断方位、低估通畅方位，恰好抹掉本方案自己要讲的问题。",
         9.2, M, "normal", 0.012),
        (0, "统筹研究范围内 14 座车站未实测，仍按 1.75 中位系数画圆，图面已注明为估算。"
            "实测值基于高德路网，尚未计入过街信号延误、围墙断点与无障碍条件，"
            "正式成果须以现场步行网络与实测出入口校核。",
         9.2, M, "normal", 0.020),
        (0, "数据与边界声明", 13, W, "bold", 0.008),
        (0, "全部空间动作均为概念建议，不替代正式规划，不构成审定、投资、建设或运营承诺。"
            "范围边界使用仓库 provisional 数据，站位与底图路网、绿地、水系取自 OpenStreetMap。"
            "官方红线、重点区边界、控规指标、道路红线、权属、市政与文保控制线均未发布；"
            "官方数据发布后必须整体复算。",
         9.2, M, "normal", 0.0),
    ]
    # grow_max: this stack is short enough that at nominal sizes it ended at
    # mid-sheet, leaving the bottom half blank. Let it scale up to the floor.
    D.fit_blocks(tx, blocks, 0.985, 0.02, leading=1.55, grow_max=1.9)

    pdf.savefig(fig)
    fig.clf()


# --------------------------------------------------------------- p2 overview
def page_overview(pdf):
    fig, pw, ph = D.new_page(PAGE)
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "廊道结构与站点体系",
        "21 座轨道站的分级设计深度",
        "02", "%02d" % TOTAL)

    mh = (ph - 2 * m - 70) * 0.60
    ax = D.ax_at(fig, m + 6, ph - m - 42 - mh, pw - 2 * m - 12, mh, PAGE)
    D.clean(ax)
    ext = pad_extent(RESEARCH, 0.06)
    D.draw_base(ax, roads, heavy, metro, green, water, rivers, ext, lw_scale=1.0)
    draw_boundaries(ax)
    lp = D.LabelPlacer(ax)
    for s in DESIGN:
        station_dot(ax, s, 6.5, core=True)
    for s in CORR:
        station_dot(ax, s, 4.2)
    for s in DESIGN:
        lp.place(s["x"], s["y"], s["name_zh"], size=8.0, weight="bold")
    for s in CORR:
        lp.place(s["x"], s["y"], s["name_zh"], size=6.6, color=D.C["mute"])
    D.scale_bar(ax, 2000, "2km")
    D.north_arrow(ax)

    tb = D.ax_at(fig, m + 6, m + 24, pw - 2 * m - 12,
                 (ph - 2 * m - 70) - mh - 12, PAGE)
    D.clean(tb, frame=False)
    tb.set_xlim(0, 1); tb.set_ylim(0, 1)
    y = 0.98
    tb.text(0, y, "总体设计范围内 · 逐站详细设计（7座，见 03-09 页）",
            fontproperties=D.font(10.5, "bold"), color=D.C["rail"], va="top")
    y -= 0.075
    for i, s in enumerate(DESIGN):
        cx = 0.0 if i < 4 else 0.51
        if i == 0 or i == 4:
            cur = y
        p = PROGRAM[s["name_zh"]]
        tb.text(cx, cur, "%s %s" % (s["name_zh"], "/".join(s["lines"]) or "S5"),
                fontproperties=D.font(8.8, "bold"), color=D.C["ink"], va="top")
        cur = D.text_block(tb, cx + 0.145, cur, p["role"], size=7.6,
                           color=D.C["mute"],
                           right=(0.49 if i < 4 else 1.0)) - 0.014

    pdf.savefig(fig)
    fig.clf()


# ---------------------------------------------------------- p3-p9 per station
def page_station(pdf, s, idx):
    fig, pw, ph = D.new_page(PAGE)
    p = PROGRAM[s["name_zh"]]
    ka = s["key_area"] or "近%s %.0f米" % (s["nearest_key_area"],
                                         s["nearest_key_area_distance_m"])
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "%s站 · %s" % (s["name_zh"], p["role"]),
        "%s · %s · %s" % ("/".join(s["lines"]) or "S5 市郊铁路",
                          "地铁" if s["mode"] == "subway" else "国铁/市郊铁路", ka),
        "%02d" % idx, "%02d" % TOTAL)

    mw = pw - 2 * m - 12
    mh = (ph - 2 * m - 70) * 0.54
    ax = D.ax_at(fig, m + 6, ph - m - 42 - mh, mw, mh, PAGE)
    D.clean(ax)
    ring15, r15 = B.walk_ring(s, 15)
    # median plus observed spread per budget: a measured isochrone has no single
    # radius, so quoting one number would misstate the drawing
    rng = {}
    for mins in (5, 10, 15):
        _, med = B.walk_ring(s, mins)
        rs = [B.reach_at(s, mins, a) for a in range(0, 360, 22)]
        rng[mins] = (round(med), round(min(rs)), round(max(rs)))
    r5, r10 = rng[5][0], rng[10][0]
    # fit to the panel aspect, else set_aspect("equal") leaves the sheet
    # half empty beside a square walk ring
    ext = D.fit_extent(pad_extent(ring15, 0.16), mw, mh)
    D.draw_base(ax, roads, heavy, metro, green, water, rivers, ext,
                show_tertiary=True, lw_scale=0.9)
    for k, g in KEYS.items():
        if g.intersects(ring15):
            xs, ys = g.exterior.xy
            ax.fill(xs, ys, color=D.C["life"], alpha=0.12, ec="none", zorder=1.5)
            ax.plot(xs, ys, color=D.C["life"], lw=1.2 * D.SCALE, zorder=7)
    for mins, alpha in ((15, 0.07), (10, 0.11), (5, 0.17)):
        ring, r = B.walk_ring(s, mins)
        xs, ys = ring.exterior.xy
        ax.fill(xs, ys, color=D.C["rail"], alpha=alpha, ec="none", zorder=8)
        ax.plot(xs, ys, color=D.C["rail"], lw=0.6 * D.SCALE, alpha=0.6, zorder=8.5)

    # Severance in the same two tiers as the A0 plates. One tier here and two
    # there would be two different diagnoses of the same station in one
    # submission.
    cut = [ln for ln in barriers if ln.intersects(ring15)]
    arter = [ln for ln in roads.get("primary", []) if ln.intersects(ring15)]
    for ln in arter:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=1.2 * D.SCALE, alpha=0.55,
                dashes=(5, 3), zorder=8.8)
    for ln in cut:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=D.C["warn"], lw=2.2 * D.SCALE, alpha=0.8, zorder=9)

    near = [o for o in stations
            if o is not s and ring15.buffer(400).contains(o["pt"])]
    for o in near:
        station_dot(ax, o, 4.5)
    station_dot(ax, s, 9.0, core=True)

    lp = D.LabelPlacer(ax)
    lp.place(s["x"], s["y"], s["name_zh"], size=10.5, weight="bold", force=True)
    for mins, ang in ((5, 90), (10, 205), (15, 325)):
        _, med = B.walk_ring(s, mins)
        # Boundary distance along this specific bearing: a measured isochrone is
        # not a circle, so one radius would put the label inside the shape on
        # long bearings and outside it on short ones.
        rr = B.reach_at(s, mins, ang) * 1.06
        lp.place(s["x"] + rr * math.cos(math.radians(ang)),
                 s["y"] + rr * math.sin(math.radians(ang)),
                 "%d分钟 中位%d米" % (mins, round(med)), size=7.0,
                 color=D.C["rail"], weight="bold", force=True)
    for o in near:
        lp.place(o["x"], o["y"], o["name_zh"], size=6.6, color=D.C["mute"],
                 force=True)
    D.scale_bar(ax, 500, "500m")
    D.north_arrow(ax)

    # Two fitted columns. A single hand-positioned run had no floor, so a
    # station with longer programme text would have walked into the footer.
    th = (ph - 2 * m - 70) - mh - 12
    tgap = 10
    tcw = (pw - 2 * m - 12 - tgap) / 2
    left = [
        (0.0, "现状问题", 10.0, D.C["warn"], "bold", 0.008),
        (0.015, p["problem"], 8.6, D.C["ink"], "normal", 0.020),
        (0.0, "切割诊断：立体 %d 段 / 平面 %d 段" % (len(cut), len(arter)),
         10.0, D.C["warn"], "bold", 0.008),
        (0.015, "实线为高速与快速路，只能靠桥隧过街，属硬断点；虚线为主干路，"
                "可过街但受信号周期影响。被切割线穿过的圈层为名义可达、实际"
                "须绕行或等待。", 8.2, D.C["mute"], "normal", 0.020),
        (0.0, "站域口径：实测等时圈", 10.0, D.C["ink"], "bold", 0.008),
        (0.015, "16 个方位实测步行路径，按 75 米/分预算反算可达边界，故站域不是圆。"
                "本站 5 分钟中位 %d 米（%d-%d）、10 分钟中位 %d 米（%d-%d）、"
                "15 分钟中位 %d 米（%d-%d）。方位差异即上方切割的直接后果。"
                "数据源：高德步行路径规划 2026-08-09。"
                % (rng[5] + rng[10] + rng[15]), 8.2, D.C["mute"], "normal", 0.0),
    ]
    right = [
        (0.0, "5 分钟核心（站城复合）", 10.0, D.C["rail"], "bold", 0.008),
        (0.015, "、".join(p["fivemin"]), 8.6, D.C["ink"], "normal", 0.018),
        (0.0, "10 分钟圈（补齐日常生活）", 10.0, D.C["rail"], "bold", 0.008),
        (0.015, "、".join(p["tenmin"]), 8.6, D.C["ink"], "normal", 0.018),
        (0.0, "15 分钟圈", 10.0, D.C["mute"], "bold", 0.008),
        (0.015, "以既有社区更新为主，不以拆迁换取形式整齐；补齐普通就业、"
                "教育医疗与公交接驳。", 8.2, D.C["mute"], "normal", 0.018),
        (0.0, "近期动作（低成本、可回退）", 10.0, D.C["park"], "bold", 0.008),
    ]
    for i, mv in enumerate(p["moves"], start=1):
        right.append((0.015, "%d. %s" % (i, mv), 8.6, D.C["ink"], "normal",
                      0.005))
    right += [
        (0.0, "", 1.0, D.C["ink"], "normal", 0.012),
        (0.0, "待实测项（本页结论的前置条件）", 10.0, D.C["mute"], "bold", 0.008),
        (0.015, "\n".join("· " + t for t in p["survey"]), 8.2, D.C["mute"],
         "normal", 0.0),
    ]
    for ci, blocks in enumerate((left, right)):
        tx = D.ax_at(fig, m + 6 + ci * (tcw + tgap), m + 24, tcw, th, PAGE)
        D.clean(tx, frame=False)
        tx.set_xlim(0, 1)
        tx.set_ylim(0, 1)
        D.fit_blocks(tx, blocks, 0.985, 0.015)

    pdf.savefig(fig)
    fig.clf()


# ------------------------------------------------------------ p10 corridor
def page_corridor(pdf):
    fig, pw, ph = D.new_page(PAGE)
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "廊道与接驳层级的 14 座站点",
        "在统筹研究范围内、总体设计范围之外：不做逐站详细设计，承担廊道衔接与接驳职责",
        "10", "%02d" % TOTAL)

    tx = D.ax_at(fig, m + 6, m + 24, pw - 2 * m - 12, ph - 2 * m - 70, PAGE)
    D.clean(tx, frame=False)
    tx.set_xlim(0, 1); tx.set_ylim(0, 1)

    blocks = [
        (0, "这些站点决定 7 座重点站的客流来向与换乘链条，因此纳入研究并给出接驳职责，"
            "但不做站域详细设计。逐站详图见 03—09 页。",
         9.0, D.C["mute"], "normal", 0.022),
    ]
    for s in CORR:
        blocks.append((0, "%s  %s" % (s["name_zh"], "/".join(s["lines"])),
                       9.4, D.C["ink"], "bold", 0.004))
        blocks.append((0.03, CORRIDOR_ROLE.get(s["name_zh"], ""),
                       8.4, D.C["mute"], "normal", 0.014))
    # 14 short entries left the bottom half of the sheet blank at nominal size
    D.fit_blocks(tx, blocks, 0.99, 0.02, leading=1.5, grow_max=1.7)

    pdf.savefig(fig)
    fig.clf()


# --------------------------------------------------------- p11 phasing/data
def page_phasing(pdf):
    fig, pw, ph = D.new_page(PAGE)
    ax0, m, ts = D.sheet_frame(
        fig, PAGE, "分期、数据校核与未解决事项",
        "实施顺序与本方案的证据边界",
        "11", "%02d" % TOTAL)

    # discrepancy map, top half
    mh = (ph - 2 * m - 70) * 0.40
    ax = D.ax_at(fig, m + 6, ph - m - 42 - mh, pw - 2 * m - 12, mh, PAGE)
    D.clean(ax)
    kd = KEYS["PROV-KEY-003"]
    dzs = [s for s in stations if s["name_zh"] == "大钟寺"][0]
    bjb = [s for s in stations if s["name_zh"] == "北京北"][0]
    focus = kd.union(dzs["pt"].buffer(500)).union(bjb["pt"].buffer(400))
    ext = pad_extent(focus, 0.18)
    D.draw_base(ax, roads, heavy, metro, green, water, rivers, ext,
                show_tertiary=True, lw_scale=0.9)
    xs, ys = kd.exterior.xy
    ax.fill(xs, ys, color=D.C["life"], alpha=0.14, ec="none", zorder=2)
    ax.plot(xs, ys, color=D.C["life"], lw=1.8 * D.SCALE, zorder=7)
    for st in (dzs, bjb):
        station_dot(ax, st, 8.0, core=True)
    dist_m = dzs["pt"].distance(kd.centroid)
    # Two distances, because one alone is misleading: the arrow measures to the
    # polygon centroid, but the nearest edge is what a reviewer checks against.
    edge_m = dzs["pt"].distance(kd)
    ax.annotate("", xy=(dzs["x"], dzs["y"]), xytext=(kd.centroid.x, kd.centroid.y),
                arrowprops=dict(arrowstyle="<->", color=D.C["warn"],
                                lw=1.6 * D.SCALE, mutation_scale=9 * D.SCALE,
                                shrinkA=3, shrinkB=3), zorder=30)
    lp = D.LabelPlacer(ax)
    lp.place((dzs["x"] + kd.centroid.x) / 2, (dzs["y"] + kd.centroid.y) / 2,
             "站位至形心 %.0f米" % dist_m, size=9.0, weight="bold",
             color=D.C["warn"])
    lp.place(dzs["x"], dzs["y"], "大钟寺站（真实站位，13号线）", size=8.0, weight="bold")
    lp.place(bjb["x"], bjb["y"], "北京北站（S5）", size=8.0, weight="bold")
    lp.place(kd.centroid.x, kd.centroid.y, "PROV-KEY-003 形心", size=7.6,
             color=D.C["life"])
    D.scale_bar(ax, 500, "500m")

    tx = D.ax_at(fig, m + 6, m + 24, pw - 2 * m - 12,
                 (ph - 2 * m - 70) - mh - 12, PAGE)
    D.clean(tx, frame=False)
    tx.set_xlim(0, 1); tx.set_ylim(0, 1)
    y = 0.99
    groups = [
        ("近期（可先行、低成本、可回退）", D.C["park"], [
            "7 站站口 200 米内连续步道、雨棚、照明与无障碍改造",
            "平交口行人相位优先与过街加密：先做学院路、西直门外大街",
            "非机动车停放正规化，清理站口占道",
            "北京北—西直门换乘通道连续化与统一导视",
        ]),
        ("中期（需专项论证）", D.C["life"], [
            "跨京藏高速、跨铁路慢行连接（学知园、六道口）",
            "学院桥立交桥下空间改造为步行连廊与公共活动场",
            "园区与校园围墙开口，形成站到园、站到校直连",
            "10 分钟圈补齐社区医疗、托育、学校与运动设施",
        ]),
        ("远期（需控规与权属落实）", D.C["rail"], [
            "站城复合核心的功能混合与租赁住房供给",
            "京张遗址公园主入口与铁路遗产门厅（北京北）",
            "径向绿廊穿透，形成连通而非封闭的绿环",
            "既有社区以更新为主，保留小商户与可承受租金",
        ]),
        ("未解决 / 需官方数据", D.C["warn"], [
            "范围口径已按官方四至确认（业主 2026-08-08）：上地、清河、西二旗不出逐站详图",
            "PROV-KEY-003 大钟寺 polygon 形心距真实站位 %.0f 米（最近边界 %.0f 米），"
            "须以官方重点区边界复核" % (dist_m, edge_m),
            "官方红线、控规指标、道路红线、权属、市政与文保控制线均未发布",
            "7 站站域已按高德步行路径实测（16 方位 784 条，2026-08-09），"
            "但过街信号延误、围墙断点、无障碍条件与实测出入口位置仍待现场核查",
        ]),
    ]
    for title, col, items in groups:
        y = D.text_block(tx, 0, y, title, size=10, color=col, weight="bold") - 0.006
        for it in items:
            y = D.text_block(tx, 0.015, y, "· " + it, size=8.4,
                             color=D.C["ink"] if col != D.C["warn"] else D.C["mute"]) - 0.004
        y -= 0.014

    pdf.savefig(fig)
    fig.clf()


def main():
    path = os.path.join(OUT, "a3-booklet.pdf")
    with PdfPages(path) as pdf:
        page_cover(pdf)
        page_overview(pdf)
        for i, s in enumerate(DESIGN, start=3):
            page_station(pdf, s, i)
        page_corridor(pdf)
        page_phasing(pdf)
    print("wrote", path)


if __name__ == "__main__":
    main()

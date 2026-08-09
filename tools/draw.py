"""Drawing primitives: CJK fonts, true A-series pages, collision-avoiding labels.

The previous submission failed on four mechanical points, all handled here:
  1. page size was A2 while claiming A0/A3  -> PAGE_MM exact A-series
  2. raster JPEG with no text layer          -> vector PDF, fonts embedded
  3. labels stacked on one baseline          -> LabelPlacer collision search
  4. lower half of the sheet left empty      -> explicit panel grid
"""
import os

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle

# --- fonts -----------------------------------------------------------------
# STHeiti Light/Medium are a matched pair from one family, and unlike the
# Hiragino .ttc collection they subset cleanly into the PDF (the Hiragino
# collection extracted correct text but rendered wrong glyphs).
CJK_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]
CJK_PATH = next((p for p in CJK_CANDIDATES if os.path.exists(p)), None)
if CJK_PATH is None:
    raise SystemExit("no CJK font found; drawings would render tofu boxes")

# Bold must be a real heavier FACE, not FontProperties.set_weight(): setting a
# weight on an fname-bound FontProperties drops the binding and matplotlib
# falls back to DejaVu, which has no CJK glyphs at all.
CJK_BOLD_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]
CJK_BOLD_PATH = next((p for p in CJK_BOLD_CANDIDATES if os.path.exists(p)), CJK_PATH)


# Type scale. matplotlib sizes are absolute points, so 9pt on an 841mm-wide
# A0 sheet is unreadable. All sizes in this codebase are authored against A4
# width and multiplied by this factor when a larger sheet is set.
SCALE = 1.0


def set_scale(page):
    """Set the type/line scale from the page size (A4 width = 1.0)."""
    global SCALE
    SCALE = PAGE_MM[page][0] / 210.0
    return SCALE


def font(size, weight="normal"):
    path = CJK_BOLD_PATH if weight == "bold" else CJK_PATH
    return FontProperties(fname=path, size=size * SCALE)


# Vector output with a real text layer. Type 42 = TrueType, keeps glyphs
# selectable and searchable instead of outlining them into paths.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["pdf.compression"] = 6
matplotlib.rcParams["axes.unicode_minus"] = False

# --- page sizes (exact A-series, mm) ---------------------------------------
MM = 1 / 25.4
PAGE_MM = {
    "A0": (841.0, 1189.0),
    "A0L": (1189.0, 841.0),
    "A3": (297.0, 420.0),
    "A3L": (420.0, 297.0),
}

# --- palette ---------------------------------------------------------------
C = dict(
    rail="#1c4f8f",
    life="#e07b39",
    park="#3f7d54",
    ink="#1a1d21",
    mute="#6b7280",
    hair="#dfe3e7",
    paper="#ffffff",
    band="#f4f6f8",
    warn="#b5452f",
)


def new_page(size="A0"):
    w, h = PAGE_MM[size]
    set_scale(size)
    fig = plt.figure(figsize=(w * MM, h * MM), dpi=300)
    fig.patch.set_facecolor(C["paper"])
    return fig, w, h


def ax_at(fig, x, y, w, h, page):
    """Place an axes using millimetre coordinates from the bottom-left."""
    pw, ph = PAGE_MM[page]
    return fig.add_axes([x / pw, y / ph, w / pw, h / ph])


def clean(ax, frame=True):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(frame)
        s.set_color(C["hair"])
        s.set_linewidth(0.6)
    ax.set_facecolor(C["paper"])
    return ax


def sheet_frame(fig, page, title, subtitle, plate, total, note=None):
    """Title block. A drawing without one is not a drawing."""
    pw, ph = PAGE_MM[page]
    m = pw * 0.035
    # font() already scales type by sheet width; ts only sizes the mm-space
    # geometry of the title block itself.
    ts = pw / 841.0
    # Title-block type is authored in A0 points and must shrink with the sheet:
    # font() re-multiplies by SCALE, so divide it back out and re-apply ts.
    fs = ts / SCALE

    fig.lines = []
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, pw)
    ax.set_ylim(0, ph)

    ax.add_patch(Rectangle((m, m), pw - 2 * m, ph - 2 * m, fill=False,
                           ec=C["ink"], lw=1.1 * ts, zorder=50))
    # header rule
    hy = ph - m - 34 * ts
    ax.plot([m, pw - m], [hy, hy], color=C["ink"], lw=0.9 * ts, zorder=50)
    ax.text(m + 6 * ts, hy + 13 * ts, title, fontproperties=font(46 * fs, "bold"),
            color=C["ink"], va="bottom", zorder=51)
    ax.text(m + 6 * ts, hy + 4.5 * ts, subtitle, fontproperties=font(20 * fs),
            color=C["mute"], va="bottom", zorder=51)
    ax.text(pw - m - 6 * ts, hy + 11 * ts, "%s / %s" % (plate, total),
            fontproperties=font(30 * fs, "bold"), color=C["rail"],
            ha="right", va="bottom", zorder=51)

    # footer: the disclaimer is a submission requirement, not decoration
    fy = m + 15 * ts
    ax.plot([m, pw - m], [fy, fy], color=C["hair"], lw=0.7 * ts, zorder=50)
    disc = ("概念方案，非法定规划成果。边界为仓库 provisional 数据，站位来自 OpenStreetMap；"
            "官方红线、控规指标与站点出入口实测数据发布后须整体复算。")
    ax.text(m + 6 * ts, fy - 6 * ts, note or disc, fontproperties=font(15 * fs),
            color=C["mute"], va="top", zorder=51)
    return ax, m, ts


class LabelPlacer:
    """Greedy collision-avoiding label placement in axes-data space.

    Tries candidate offsets around the anchor and keeps the first that does
    not overlap an already-placed box. This is what the old raster figures
    lacked: every ring label was written at the same anchor.
    """

    def __init__(self, ax, pad=1.06):
        self.ax = ax
        self.boxes = []
        self.pad = pad

    def _overlaps(self, box):
        x0, y0, x1, y1 = box
        for bx0, by0, bx1, by1 in self.boxes:
            if x0 < bx1 and bx0 < x1 and y0 < by1 and by0 < y1:
                return True
        return False

    def place(self, x, y, text, size=7.0, weight="normal", color=None,
              prefer=None, halo=True, zorder=60, force=False):
        """Place `text` near (x, y), or return None if every candidate collides.

        force=True keeps the label even when it must overlap — use it for the
        subject of the sheet, where a missing name is worse than a collision.
        """
        fp = font(size, weight)
        # estimate box in data units from the current view
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        bb = self.ax.get_window_extent()
        if bb.width <= 0 or bb.height <= 0:
            return None
        upp_x = (x1 - x0) / bb.width      # data units per pixel
        upp_y = (y1 - y0) / bb.height
        px_per_pt = self.ax.figure.dpi / 72.0
        # measure per line: a two-line label reserved as one line is what let
        # the PROV-KEY-003 annotation sit on top of the 北京北 station name
        rows = text.split("\n")
        def _w(t):
            n_cjk = sum(1 for ch in t if ord(ch) > 0x2E80)
            return size * (n_cjk + 0.55 * (len(t) - n_cjk))
        # font() renders at size*SCALE, so the box must be measured at
        # size*SCALE too. Without it, boxes on an A0 sheet (SCALE≈4) came out
        # a quarter of the real glyph size and the collision test never fired.
        pt = size * SCALE
        w_pt = max(_w(t) for t in rows) / size * pt
        h_pt = pt * 1.25 * len(rows)
        w = w_pt * px_per_pt * upp_x * self.pad
        h = h_pt * px_per_pt * upp_y * self.pad
        off = pt * px_per_pt * 0.62

        cands = list(prefer) if prefer else []
        if not cands:
            # eight anchors at the nominal offset, then the same eight pushed
            # further out. On a dense sheet the near ring is often fully
            # blocked, and dropping the label is worse than nudging it.
            for mult in (1.0, 1.9, 3.0):
                ox, oy = off * upp_x * mult, off * upp_y * mult
                cands += [
                    ("left", "center", ox, 0),
                    ("right", "center", -ox, 0),
                    ("center", "bottom", 0, oy),
                    ("center", "top", 0, -oy),
                    ("left", "bottom", ox * 0.8, oy * 0.8),
                    ("right", "bottom", -ox * 0.8, oy * 0.8),
                    ("left", "top", ox * 0.8, -oy * 0.8),
                    ("right", "top", -ox * 0.8, -oy * 0.8),
                ]
        for ha, va, dx, dy in cands:
            ax_ = x + dx
            ay = y + dy
            bx0 = ax_ if ha == "left" else (ax_ - w if ha == "right" else ax_ - w / 2)
            by0 = ay if va == "bottom" else (ay - h if va == "top" else ay - h / 2)
            box = (bx0, by0, bx0 + w, by0 + h)
            if self._overlaps(box):
                continue
            if not (x0 <= box[0] and box[2] <= x1 and y0 <= box[1] and box[3] <= y1):
                continue
            self.boxes.append(box)
            t = self.ax.text(ax_, ay, text, fontproperties=fp, ha=ha, va=va,
                             color=color or C["ink"], zorder=zorder)
            if halo:
                import matplotlib.patheffects as pe
                t.set_path_effects([pe.withStroke(linewidth=2.0, foreground="white")])
            return t
        if force:
            # last resort: accept the overlap, but keep the label inside the
            # axes. A station sitting near the panel edge has every candidate
            # off-sheet, so clamp rather than drop.
            for ha, va, dx, dy in cands:
                ax_, ay = x + dx, y + dy
                bx0 = ax_ if ha == "left" else (ax_ - w if ha == "right" else ax_ - w / 2)
                by0 = ay if va == "bottom" else (ay - h if va == "top" else ay - h / 2)
                box = (bx0, by0, bx0 + w, by0 + h)
                if not (x0 <= box[0] and box[2] <= x1
                        and y0 <= box[1] and box[3] <= y1):
                    continue
                self.boxes.append(box)
                t = self.ax.text(ax_, ay, text, fontproperties=fp, ha=ha,
                                 va=va, color=color or C["ink"], zorder=zorder)
                if halo:
                    import matplotlib.patheffects as pe
                    t.set_path_effects([pe.withStroke(linewidth=2.6,
                                                      foreground="white")])
                return t
            bx0 = min(max(x - w / 2, x0), x1 - w)
            by0 = min(max(y + off * upp_y, y0), y1 - h)
            self.boxes.append((bx0, by0, bx0 + w, by0 + h))
            t = self.ax.text(bx0, by0, text, fontproperties=fp, ha="left",
                             va="bottom", color=color or C["ink"],
                             zorder=zorder)
            if halo:
                import matplotlib.patheffects as pe
                t.set_path_effects([pe.withStroke(linewidth=2.6,
                                                  foreground="white")])
            return t
        return None  # dropped rather than overlapped

    def reserve(self, x0, y0, x1, y1):
        self.boxes.append((x0, y0, x1, y1))


def draw_base(ax, roads, heavy, metro, green, water, rivers, extent,
              road_classes=("motorway", "trunk", "primary", "secondary"),
              show_tertiary=False, lw_scale=1.0):
    """Paint the shared base map inside a metric extent (minx,miny,maxx,maxy)."""
    from basemap import ROAD_STYLE
    minx, miny, maxx, maxy = extent
    for g in green:
        if g.bounds[2] < minx or g.bounds[0] > maxx:
            continue
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color="#e8f0e6", ec="none", zorder=0.5)
    for g in water:
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color="#dbe7f0", ec="none", zorder=0.6)
    for ln in rivers:
        xs, ys = ln.xy
        ax.plot(xs, ys, color="#bcd3e3", lw=1.6 * lw_scale * SCALE, zorder=0.7)
    ls = lw_scale * SCALE  # stroke weight must grow with the sheet too
    classes = list(road_classes) + (["tertiary"] if show_tertiary else [])
    for cls in classes:
        st = ROAD_STYLE[cls]
        for ln in roads.get(cls, []):
            xs, ys = ln.xy
            ax.plot(xs, ys, color=st["color"], lw=st["lw"] * ls,
                    solid_capstyle="round", zorder=st["z"])
    for ln in metro:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=C["rail"], lw=0.7 * ls, alpha=0.5, zorder=4)
    for ln in heavy:
        xs, ys = ln.xy
        ax.plot(xs, ys, color=C["ink"], lw=1.5 * ls, alpha=0.85, zorder=4.5)
        ax.plot(xs, ys, color="white", lw=0.5 * ls, alpha=0.9,
                dashes=(4, 4), zorder=4.6)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")


def fit_extent(ext, w_mm, h_mm):
    """Expand a metric extent to the axes aspect so scale stays isotropic.

    Without this, `set_aspect("equal")` shrinks the axes box to the data
    aspect and leaves a third of the sheet blank — a square walk-ring in a
    landscape panel wastes everything to its right.
    """
    minx, miny, maxx, maxy = ext
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    dw, dh = maxx - minx, maxy - miny
    target = w_mm / h_mm
    if dw / dh < target:
        dw = dh * target
    else:
        dh = dw / target
    return (cx - dw / 2, cy - dh / 2, cx + dw / 2, cy + dh / 2)


def wrap_cjk(text, width):
    """Wrap mixed CJK/latin text to `width` CJK-equivalent columns.

    CJK glyphs are full-width, latin roughly half, so a plain len() based wrap
    produces ragged lines on a sheet that mixes both.
    """
    def cw(ch):
        return 1.0 if ord(ch) > 0x2E80 else 0.55

    def is_word(ch):
        # '/' '.' '-' bind so "m/min", "1.35" and "5/10/15" stay one token
        return ord(ch) <= 0x2E80 and (ch.isalnum() or ch in "/.-")

    # Tokenise first: CJK breaks anywhere, but a latin/number run must not be
    # split, or "278m" wraps as "27" + "8m" and "OpenStreetMap" as "Op" +
    # "enStreetMap" — both appeared on the A0 sheets.
    toks, buf = [], []
    for ch in text:
        if is_word(ch):
            buf.append(ch)
            continue
        if buf:
            toks.append("".join(buf)); buf = []
        toks.append(ch)
    if buf:
        toks.append("".join(buf))

    # CJK line-break rules: these may not open a line (禁则处理). Letting
    # them through put "，是本站…" and "。此处…" at the left margin.
    NO_LINE_START = "，。、；：？！）》」』】〉”’%…·"

    lines, cur, w = [], [], 0.0
    for tok in toks:
        if tok == "\n":
            lines.append("".join(cur)); cur, w = [], 0.0
            continue
        tw = sum(cw(c) for c in tok)
        if w + tw > width and cur:
            if tok in NO_LINE_START:
                # let the punctuation hang past the column rather than start
                # the next line with it
                cur.append(tok)
                lines.append("".join(cur)); cur, w = [], 0.0
                continue
            lines.append("".join(cur)); cur, w = [], 0.0
            if tok == " ":  # never open a line with a stranded space
                continue
        if tw > width and not cur:
            # a single token longer than the column: hard-split it, no choice
            for c in tok:
                if w + cw(c) > width and cur:
                    lines.append("".join(cur)); cur, w = [], 0.0
                cur.append(c); w += cw(c)
            continue
        cur.append(tok); w += tw
    if cur:
        lines.append("".join(cur))
    return lines


def fit_blocks(ax, blocks, y_start, y_floor, right=1.0, leading=1.5,
               shrink_min=0.62, grow_max=1.0):
    """Lay out a list of blocks, auto-scaling type until they fit the panel.

    blocks: list of (x, text, size, color, weight, gap_after)
    Hand-tuning each font size per panel does not survive the longest entry —
    this measures the whole stack and scales it once, uniformly.

    grow_max > 1.0 also lets a short stack scale *up*. Without it a sparse page
    keeps its nominal sizes and leaves the bottom half of the sheet blank,
    which reads as an unfinished sheet rather than a deliberate one.
    """
    def bottom(factor):
        y = y_start
        for x, text, size, color, weight, gap in blocks:
            bb = ax.get_window_extent()
            px_per_pt = ax.figure.dpi / 72.0
            glyph_px = size * factor * SCALE * px_per_pt
            cols = max(int(max(bb.width * (right - x), 1.0) / glyph_px), 8)
            n = len(wrap_cjk(text, cols))
            y -= n * (glyph_px * leading) / max(bb.height, 1e-6) + gap
        return y

    factor = 1.0
    for _ in range(14):
        if bottom(factor) >= y_floor or factor <= shrink_min:
            break
        factor *= 0.94
    if grow_max > 1.0 and bottom(factor) >= y_floor:
        while factor < grow_max:
            nxt = min(factor * 1.03, grow_max)
            if bottom(nxt) < y_floor:
                break
            factor = nxt
    y = y_start
    for x, text, size, color, weight, gap in blocks:
        y = text_block(ax, x, y, text, size * factor, color, leading=leading,
                       weight=weight, right=right) - gap
    return y, factor


def text_block(ax, x, y, text, size, color, leading=1.5,
               weight="normal", va="top", right=1.0):
    """Draw wrapped text in axes-fraction coords; return y below the block.

    The wrap width is derived from the real axes width so text cannot run off
    the sheet: columns = available_width_pt / glyph_width_pt.
    """
    fp = font(size, weight)
    bb = ax.get_window_extent()
    px_per_pt = ax.figure.dpi / 72.0
    glyph_px = size * SCALE * px_per_pt
    avail_px = max(bb.width * (right - x), 1.0)
    cols = max(int(avail_px / glyph_px), 8)
    step = (glyph_px * leading) / max(bb.height, 1e-6)
    lines = wrap_cjk(text, cols)
    for i, ln in enumerate(lines):
        ax.text(x, y - i * step, ln, fontproperties=fp, color=color,
                va=va, transform=ax.transAxes)
    return y - len(lines) * step


def scale_bar(ax, length_m=1000, label=None, loc=(0.06, 0.045)):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    bx = x0 + (x1 - x0) * loc[0]
    by = y0 + (y1 - y0) * loc[1]
    ax.plot([bx, bx + length_m], [by, by], color=C["ink"], lw=2.2 * SCALE, zorder=70,
            solid_capstyle="butt")
    for xx in (bx, bx + length_m):
        ax.plot([xx, xx], [by, by + (y1 - y0) * 0.008], color=C["ink"],
                lw=1.2 * SCALE, zorder=70)
    ax.text(bx + length_m / 2, by + (y1 - y0) * 0.012,
            label or ("%dm" % length_m), fontproperties=font(6.5),
            ha="center", va="bottom", color=C["ink"], zorder=70)


def north_arrow(ax, loc=(0.94, 0.9)):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * loc[0]
    y = y0 + (y1 - y0) * loc[1]
    d = (y1 - y0) * 0.035
    ax.annotate("", xy=(x, y + d), xytext=(x, y - d),
                arrowprops=dict(arrowstyle="-|>", color=C["ink"],
                                lw=1.3 * SCALE, mutation_scale=10 * SCALE),
                zorder=70)
    ax.text(x, y + d * 1.15, "N", fontproperties=font(7.5, "bold"),
            ha="center", va="bottom", color=C["ink"], zorder=70)

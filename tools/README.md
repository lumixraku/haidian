# tools — 图纸生成器

`submissions/lumixraku/rail-life-rings/` 里的两份 PDF 和五张图，全部由这个目录下的脚本生成。放在仓库里是为了让图纸可以从 clone 复现，而不是只存在于某台机器上。

> **这个目录只存在于 `lumixraku` 的 fork。** `scripts/validate_submission.py` 规定参赛者 PR 只能改 `submissions/<github-login>/`，投稿目录本身又是一份封闭白名单（只允许 `.pdf`、图片、指定的 geojson 与 json），`.py` 没有位置可放。所以往上游提 PR 时，这个目录和根目录 `README.md`、`progress.md` 一样必须从差异里剔除。

## 跑一遍

```bash
python -m venv .venv
.venv/bin/pip install -r tools/requirements.txt
.venv/bin/python tools/make_a0.py        # -> tools/out/a0-boards.pdf   9 张 A0
.venv/bin/python tools/make_a3.py        # -> tools/out/a3-booklet.pdf  11 页 A3
.venv/bin/python tools/make_figures.py   # -> tools/out/figures/*.png   5 张
```

生成结果写在 `tools/out/`，不进版本库。确认无误后再手工拷进投稿目录，并重算 `manifest.json` 里的 `sha256`。

版本必须按 `requirements.txt` 钉住：`draw.py` 的标签避让是按 matplotlib 的文字度量算的，换一个 minor 版本，标签落点就可能不同。

## 复现性

`tools/` 版本生成的文件与投稿目录里已装的文件逐页比对：**两份 PDF 每一页的文字层与矢量图元完全一致，五张 PNG 逐像素一致**。PDF 的 sha256 仍然不同，因为 matplotlib 会写入生成时间戳；除此之外没有差异。

## 文件

| 文件 | 作用 |
| --- | --- |
| `basemap.py` | 底图与投影。所有几何投到 EPSG:32650（UTM 50N），距离与步行圈按米算而不是按度。含 `walk_ring()`：`半径 = 分钟 × 75 米/分 ÷ 1.35 绕行系数` |
| `draw.py` | 三个生成器共用的绘图层：页面框、标签避让、CJK 折行、图例、比例尺、指北针。**改这里会同时影响 A0、A3 和五张图** |
| `make_a0.py` | 9 张 A0 展板：`L-01` 廊道结构与 21 站分级，`L-02`～`L-08` 逐站一整张，`L-09` 重点区原型与数据校核 |
| `make_a3.py` | 11 页 A3 方案册：封面、廊道总览、7 站逐站一页、廊道接驳、分期 |
| `make_figures.py` | README 与 `proposal.md` 用的五张 PNG。文件名由 `REQUIRED_PROPOSAL_IMAGE_PATHS` 固定，不能改 |
| `station_program.py` | 7 座逐站车站的功能配置与 14 座廊道站的接驳角色，纯数据 |
| `audit.py` | 版式审计：逐 span 检查文字越界与文字框重叠 |
| `fetch_base.py` / `fetch_gw.py` | 从 Overpass 拉 OSM 底图到 `data/`。`data/` 已有文件就跳过，正常情况不需要再跑 |

### `draw.py` 里两个容易踩的地方

- `SCALE = 页宽mm / 210`（A4 宽为 1.0），`font(size)` 实际渲染在 `size * SCALE`。**任何手算文字尺寸的地方都必须同样乘 `SCALE`**，否则在 A0（`SCALE`≈4）上算出来的框只有真实字号的四分之一，避让判定几乎不触发。
- `set_aspect("equal")` 会把坐标轴缩到数据比例，留下大片空白。要用 `fit_extent(ext, w_mm, h_mm)` 把范围反过来撑到面板比例。

## 数据

`data/` 下是生成时用的输入：

- `stations.geojson` — 21 座车站，含真实坐标、线路、`scope_level`。**坐标来自 OpenStreetMap，是 provisional 数据**，须以实测出入口替换后复算站域。
- `lines_by_station.json` — 车站线路对照。
- `osm_roads.json`（2343 条分级道路）、`osm_rail.json`（244 条轨道）、`osm_green.json`、`osm_water.json` — Overpass 导出，bbox `39.925,116.295,40.045,116.385`。© OpenStreetMap contributors，ODbL。

范围边界不在这里：`basemap.py` 直接读仓库自带的 `brief/site-package/geometry/provisional_boundaries.geojson`。这份边界是 provisional，不是官方红线。

字体用系统的 STHeiti Light / STHeiti Medium（macOS `/System/Library/Fonts/STHeiti Light.ttc` 与 `Medium.ttc`）。两者必须是**两个独立字体文件**：用 `set_weight()` 让 matplotlib 丢掉绑定回退到 DejaVu，而 DejaVu 没有中文字形。非 macOS 环境需要在 `draw.py` 里换成本机可用的中文字体文件。

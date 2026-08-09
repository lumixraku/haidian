"""Per-station design programme for the 7 stations inside the 11.4km² design area.

This is the content the old submission did not have: it placed three TOD cores at
the geometric centres of the key-area polygons and never named a station. Each
entry below is anchored to a real station, its real lines, and the severance
problem visible in the OSM base map around it.

Every entry is a conceptual design proposal pending official survey — the
`survey` field names what must be measured before any of it is actionable.
"""

# role:      what this station is for in the corridor
# problem:   the concrete first-mile failure at this station today
# fivemin:   what goes in the 5-minute core
# tenmin:    what the 10-minute ring must add
# moves:     near-term physical actions (the "具体到站点" the owner asked for)
# survey:    what must be measured before this is more than a proposal
PROGRAM = {
    "学知园": dict(
        role="众智园北端研发接驳门户",
        problem="站点位于重点区内部，但东侧京藏高速与北五环形成双重切割，园区与站点间缺连续步行面。",
        fivemin=["通勤接驳厅", "早餐与夜间餐饮", "共享实验与中试展示", "轮班工作者休息"],
        tenmin=["青年与普通职工租赁住房", "社区医疗与托育", "便利商业", "低速接驳测试道"],
        moves=["跨京藏高速人行天桥或地道加宽，取消绕行",
               "站口 200m 内连续无障碍步道与雨棚",
               "园区围墙开口，形成站到园直连"],
        survey=["高速两侧步行流量与绕行距离", "园区权属与开口可行性", "站厅高峰客流"],
    ),
    "六道口": dict(
        role="原点社区北门户与校城缝合点",
        problem="紧邻 AI 原点社区边界（684m）但被学院路主干与校园围墙夹持，过街等待长。",
        fivemin=["平价餐饮", "自习与夜间学习", "便利店与药房", "非机动车集中停放"],
        tenmin=["学校与社区医疗", "成果发布与共享会议", "普通住房更新", "运动设施"],
        moves=["学院路平交口行人相位优先，压缩等待",
               "校园东南角围墙开口接入站口",
               "站口自行车停放正规化，清理占道"],
        survey=["过街延误实测", "校园开放意愿与管理边界", "非机动车停放缺口"],
    ),
    "学院桥": dict(
        role="AI 原点社区核心站城复合核",
        problem="站点落在重点区内，但立交桥区人车混行、导视缺失，桥下空间闲置。",
        fivemin=["站城复合门厅", "灵活办公", "社区服务与托育", "日常商业首层"],
        tenmin=["综合商场与就业空间", "医院或社区医疗", "租赁住房与公寓", "径向绿廊入口"],
        moves=["立交桥下空间改造为有照明的步行连廊与公共活动场",
               "四向连续过街与统一导视",
               "径向绿廊穿透，替代封闭绿带"],
        survey=["桥下空间权属与结构条件", "夜间照明与安全基线", "现状容积与拆改留判断"],
    ),
    "西土城": dict(
        role="学研与生活混合的中段站",
        problem="距原点社区 958m，处于两重点区之间的接续段，沿线业态单一、夜间冷清。",
        fivemin=["日常商业与餐饮", "社区服务点", "共享自习", "接驳候车"],
        tenmin=["普通住房更新", "学校与幼托", "小型运动场地", "沿街就业空间"],
        moves=["沿站步行街段首层业态激活，避免纯办公",
               "补齐夜间照明与连续遮阴",
               "接入南北慢行脊"],
        survey=["沿街业态与租金基线", "夜间人流与安全感调查", "住房更新意愿"],
    ),
    "蓟门桥": dict(
        role="南段承接站与绿脊节点",
        problem="距第三重点区 1.8km，位于慢行脊中段，主干路切断东西向步行联系。",
        fivemin=["接驳与便民服务", "早餐与便利", "公共休憩", "非机动车换乘"],
        tenmin=["社区医疗", "普通住房与就业混合", "公园入口与运动", "学校接送空间"],
        moves=["东西向过街加密，缩短绕行",
               "绿脊在此段连通，不做封闭隔离带",
               "站口公共休憩与遮阴"],
        survey=["东西向步行断点普查", "绿地可穿透性评估", "过街需求分布"],
    ),
    "北京北": dict(
        role="京张遗产门户与市郊铁路接口（S5）",
        problem="位于第三重点区临时 polygon 内，是市郊铁路而非地铁站；与西直门地铁换乘步行距离长、指引弱。",
        fivemin=["铁路遗产门厅与文化展示", "全时商业与餐饮", "换乘导视枢纽", "行李友好动线"],
        tenmin=["公共服务与国际交往", "租赁住房", "灵活办公", "遗址公园入口"],
        moves=["北京北—西直门换乘通道连续化与统一导视",
               "京张遗址公园在此设主入口",
               "站前广场机动车与步行分离"],
        survey=["换乘步行时间与迷路点实测", "铁路用地权属与文保控制线", "站前交通组织"],
    ),
    "西直门": dict(
        role="南端城市级换乘锚点（2/4/13 号线）",
        problem="三线换乘且紧邻研究范围南界，站域被西直门外大街与立交切割，属高强度既有建成区。",
        fivemin=["三线换乘优化", "全时商业", "公共服务窗口", "夜间照明与安全"],
        tenmin=["普通就业岗位", "既有社区更新", "医疗与教育补齐", "非机动车与公交接驳"],
        moves=["换乘导视与步行连续性优先，不做大拆大建",
               "西直门外大街过街与非机动车路权改善",
               "既有社区以更新为主，保留小商户"],
        survey=["三线换乘客流与瓶颈", "既有社区更新意愿与租金承受力", "小商户经营现状"],
    ),
}

# corridor-level stations: interchange role only, no per-station detailed design
CORRIDOR_ROLE = {
    "林萃桥": "北端接驳，8 号线换乘进入研究范围",
    "北沙滩": "东北向接驳，15 号线",
    "清华东路西口": "校城接驳，15 号线",
    "五道口": "高校就业与生活锚点，13 号线（距原点社区 879m）",
    "知春路": "10/13 换乘，西向就业接驳",
    "知春里": "10 号线，居住接驳",
    "牡丹园": "10/19 换乘，东侧居住接驳",
    "北太平庄": "19 号线，南段居住接驳",
    "人民大学": "4 号线，高校与就业接驳",
    "大钟寺": "13 号线；真实站位在重点区临时 polygon 以北约 1.7km，须以实测站位复核",
    "魏公村": "4 号线，高校接驳",
    "积水潭": "2/19 换乘，南端城市接驳",
    "国家图书馆": "4/9/16 换乘，西南向接驳",
    "新街口": "4 号线，南端生活接驳",
}

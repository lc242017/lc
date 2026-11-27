# -*- coding: utf-8 -*-
"""
云购生活 · 智能经营问答（Streamlit · 多年度增强）
手册步骤4：NL2SQL 后端 + ECharts 渲染的对话闭环
运行：streamlit run streamlit_app.py

- 问答支持全部年份（2022-2026）；2024 真实、其余模拟扩展，界面显式标注。
- 预测支持按年份建模 + 输入天数自动输出 + 按年份检索预测结果。
"""
import json
import os
import re
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from nl2sql import answer, extract_days

YEARS = [2022, 2023, 2024, 2025, 2026]
REAL_YEAR = 2024


@st.cache_data(show_spinner=False)
def _echarts_script():
    """优先使用本地 ECharts（无外网依赖），失败时回退 CDN。"""
    for path in ("/app/echarts.min.js", "echarts.min.js"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return "<script>" + f.read() + "</script>"
        except Exception:
            continue
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>'


@st.cache_data(show_spinner=False)
def _annual_data():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "echarts", "data", "multi_year.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


st.set_page_config(page_title="云购生活·智能经营问答", page_icon="💬", layout="wide")

st.title("💬 云购生活 · 智能经营问答")
st.caption("基于 ADS 指标层的 NL2SQL 对话应用 · 支持全部年份（2022-2026）· "
           "2024 为 Hive 真实数据，其余年份为模拟扩展")

# 示例问题（覆盖年份）
examples = ["2024年总体GMV", "2025年销售趋势", "2023年品类排行",
            "2024年门店Top10", "预测未来30天GMV", "预测2026年"]

# session_state 初始化
if "question" not in st.session_state:
    st.session_state.question = ""
if "forecast_days" not in st.session_state:
    st.session_state.forecast_days = 7
if "query_year" not in st.session_state:
    st.session_state.query_year = "全部年份"
if "forecast_year" not in st.session_state:
    st.session_state.forecast_year = "全部年份"

# ---- 全局年份选择 ----
yr_col, hint_col = st.columns([1, 3])
with yr_col:
    sel_year = st.selectbox("查询年份", ["全部年份"] + YEARS,
                            key="query_year", format_func=lambda x: str(x))
with hint_col:
    st.caption("📅 选择年份后，未写明年份的问题按该年份查询；"
               "问题中写了年份（如“2025年GMV”）则优先以问题为准。")

q = st.text_input("请输入你的问题，例如：2025年广东省销售额是多少？",
                  value=st.session_state.question)
cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if cols[i].button(ex, use_container_width=True):
        q = ex
        st.session_state.question = ex

# 预测类问题：天数 + 基准年份输入
is_forecast_q = bool(q and re.search(
    r"预测|预估|预计|forecast|未来\s*\d{1,3}\s*天", q, re.I))
if q and st.session_state.get("_last_q") != q:
    st.session_state.forecast_days = extract_days(q, 7)
    st.session_state._last_q = q
forecast_days = st.session_state.forecast_days
if is_forecast_q:
    fc1, fc2, fc3 = st.columns([1, 1, 3])
    with fc1:
        forecast_days = st.number_input(
            "预测未来天数（天）", min_value=1, max_value=365, step=1,
            key="forecast_days", help="输入天数后自动输出未来每天的预测 GMV")
    with fc2:
        st.selectbox("预测基准年份", ["全部年份"] + YEARS, key="forecast_year",
                     help="以该年份末为起点向外预测；全部年份=用完整历史")
    with fc3:
        st.caption("🚀 改天数或基准年份即自动重算，无需手填数值；"
                   "也可在问题里写“预测未来30天”“2024年预测14天”。")

year_arg = None if sel_year == "全部年份" else sel_year
if is_forecast_q and st.session_state.forecast_year != "全部年份":
    year_arg = st.session_state.forecast_year

if q:
    st.session_state.question = q
    with st.spinner("正在解析问题并查询 ADS 指标层 ..."):
        r = answer(q, future_days=forecast_days if is_forecast_q else None,
                   year=year_arg)

    used_year = r.get("year")
    year_badge = "全部年份" if used_year is None else str(used_year)
    src_note = " · 🟢 2024 真实数据" if used_year == REAL_YEAR else (
        " · 🟡 模拟扩展数据" if used_year in YEARS else " · 🟢2024真实 + 🟡其余模拟")
    st.markdown(f"**你的问题**：{r['question']}　　📅 **查询年份**：{year_badge}{src_note}")

    with st.expander("🔍 查看自动生成的 SQL", expanded=True):
        st.code(r["sql"], language="sql")

    st.subheader(f"📊 {r['title']}（{year_badge}）")

    chart = r["chart"]
    cols_, rows = r["columns"], r["rows"]
    display_rows = rows

    # ---- 预测：第3周手册步骤3标准建模（按年份 + 输入天数自动输出）----
    model = r.get("model")
    if chart == "forecast" and model and "error" not in model:
        st.caption(f"📈 数据源：{model['data_source']} · "
                   f"训练 {model['train_days']} 天 / 测试 {model['test_days']} 天 "
                   f"({model['test_range'][0]} ~ {model['test_range'][1]})")

        st.markdown("##### 📐 模型评估（测试集）")
        m = model["model"]
        k1, k2, k3 = st.columns(3)
        k1.metric("MAE", f"{m['MAE']:,.2f} 元")
        k2.metric("RMSE", f"{m['RMSE']:,.2f} 元")
        k3.metric("MAPE", f"{m['MAPE(%)']:.2f}%")
        st.caption(f"基线对比 → lag1：MAE {model['baseline_lag1']['MAE']:,.0f} / "
                   f"MAPE {model['baseline_lag1']['MAPE(%)']:.2f}%；"
                   f"ma7：MAE {model['baseline_ma7']['MAE']:,.0f} / "
                   f"MAPE {model['baseline_ma7']['MAPE(%)']:.2f}%")

        # 测试集预测 vs 真实
        ac_rows = model["actual_rows"]
        cmp_opt = {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["实际 GMV", "模型预测"], "bottom": 0},
            "grid": {"left": 60, "right": 30, "top": 30, "bottom": 50},
            "xAxis": {"type": "category", "data": [x["date"][5:] for x in ac_rows]},
            "yAxis": {"type": "value", "name": "元"},
            "series": [
                {"name": "实际 GMV", "type": "line", "smooth": True,
                 "data": [x["actual"] for x in ac_rows], "itemStyle": {"color": "#4fd1ff"}},
                {"name": "模型预测", "type": "line", "smooth": True,
                 "data": [x["pred"] for x in ac_rows],
                 "lineStyle": {"type": "dashed", "width": 2}, "itemStyle": {"color": "#ff7a45"}},
            ],
        }
        cmp_html = f"""
        <div id="cmp" style="width:100%;height:320px;"></div>
        {_echarts_script()}
        <script>var c=echarts.init(document.getElementById('cmp'));
        c.setOption({json.dumps(cmp_opt, ensure_ascii=False)});
        window.addEventListener('resize',()=>c.resize());</script>
        """
        components.html(cmp_html, height=340, scrolling=False)

        # ---- 未来预测 + 按年份检索 ----
        fut_all = model["future_rows"]
        fut_years = sorted({x["year"] for x in fut_all})
        fy_col, _ = st.columns([1, 3])
        with fy_col:
            view_year = st.selectbox("查看预测年份", ["全部预测年份"] + fut_years,
                                     key="view_forecast_year")
        fut = fut_all if view_year == "全部预测年份" else [
            x for x in fut_all if x["year"] == view_year]

        hist = model["history"][-30:]
        hist_labels = [h["date"][5:] for h in hist]
        fut_labels = [f["date"][5:] for f in fut]
        all_labels = hist_labels + fut_labels
        hist_vals = [round(h["gmv"], 2) for h in hist]
        hist_series = hist_vals + [None] * len(fut)
        pred_series = [None] * (len(hist) - 1) + [hist_vals[-1]] + [f["pred"] for f in fut]
        fut_opt = {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["历史实际", "未来预测"], "bottom": 0},
            "grid": {"left": 60, "right": 30, "top": 30, "bottom": 50},
            "xAxis": {"type": "category", "data": all_labels, "axisLabel": {"interval": 4}},
            "yAxis": {"type": "value", "name": "元", "scale": True},
            "series": [
                {"name": "历史实际", "type": "line", "smooth": True, "data": hist_series,
                 "areaStyle": {"opacity": 0.12}, "itemStyle": {"color": "#4fd1ff"}},
                {"name": "未来预测", "type": "line", "smooth": True, "data": pred_series,
                 "lineStyle": {"type": "dashed", "width": 2}, "itemStyle": {"color": "#ff7a45"}},
            ],
        }
        fut_html = f"""
        <div id="fut" style="width:100%;height:320px;"></div>
        {_echarts_script()}
        <script>var c=echarts.init(document.getElementById('fut'));
        c.setOption({json.dumps(fut_opt, ensure_ascii=False)});
        window.addEventListener('resize',()=>c.resize());</script>
        """
        components.html(fut_html, height=340, scrolling=False)

        # 输入天数 → 自动输出每天预测值（可按年份筛选）
        view_label = "全部预测年份" if view_year == "全部预测年份" else f"{view_year} 年"
        st.markdown(f"##### 🔮 {view_label} · 未来 {len(fut)} 天预测值（自动输出）")
        f1, f2, f3 = st.columns(3)
        f1.metric("日均预测 GMV", f"{sum(x['pred'] for x in fut)/len(fut):,.2f} 元" if fut else "-")
        f2.metric("区间累计 GMV", f"{sum(x['pred'] for x in fut):,.2f} 元")
        f3.metric("预测区间", f"{fut[0]['date']} ~ {fut[-1]['date']}" if fut else "-")
        fut_df = pd.DataFrame(
            [[x["date"], x["year"],
              "周末" if x["is_weekend"] else "工作日",
              "会员日" if x["is_promo"] else "普通日",
              f"{x['pred']:,.2f}"] for x in fut],
            columns=["日期", "年份", "星期类型", "营销类型", "预测 GMV（元）"])
        st.dataframe(fut_df, use_container_width=True)
        st.caption("预测值由 lag1/ma7 + 周末/会员日特征线性回归滚动生成，"
                   "改天数/基准年份或用“查看预测年份”筛选即自动重算。"
                   "趋势参考，遇大促/节假日需人工修正。")

        # 模型边界说明
        with st.expander("⚠️ 模型适用边界与评估说明", expanded=False):
            seg = model["segments"]
            st.markdown(f"""
            - **评估口径**：末 {model['test_days']} 天作测试集，训练集 {model['train_days']} 天，
              特征为 {', '.join(model['features'])}；基准年份 {model['year_label']}。
            - **精度**：MAE {m['MAE']:,.0f} 元 / MAPE {m['MAPE(%)']:.2f}%。
              ma7 移动平均基线 MAPE {model['baseline_ma7']['MAPE(%)']:.2f}%，
              模型与其接近——简单基线已具竞争力，复杂模型未显著胜出属正常现象。
            - **分段表现**：普通日 MAPE {seg['普通日']['MAPE(%)']:.2f}%、
              周末 {seg['周末']['MAPE(%)']:.2f}%、
              会员日/大促 {seg['会员日/大促']['MAPE(%)']:.2f}%。
            - **年份口径**：2024 为 Hive 真实数据；2022/2023/2025/2026 为基于 2024 的模拟扩展，
              预测结果仅供多年度趋势演示，不可作为真实经营决策依据。
            - **外推风险**：线性回归对突变（大促、节假日、异常流量）响应滞后，落地需业务复核。
            """)

        display_rows = [[x["date"], f"{x['actual']:.2f}", f"{x['pred']:.2f}"]
                        for x in ac_rows]

    # ---- KPI：指标卡 + 跨年对比图（所有年份都有图）----
    if chart == "kpi" and rows:
        annual = _annual_data()
        yk = [annual["kpi"][str(y)][0] for y in YEARS]
        st.markdown("##### 📊 各年份 GMV / 订单数对比（🟢2024真实 · 🟡其余模拟）")
        yopt = {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["GMV", "订单数"], "bottom": 0},
            "grid": {"left": 70, "right": 60, "top": 40, "bottom": 50},
            "title": {"text": "当前查询" if used_year is None else f"{used_year} 年",
                      "left": "center", "textStyle": {"fontSize": 13}},
            "xAxis": {"type": "category", "data": [str(y) for y in YEARS]},
            "yAxis": [
                {"type": "value", "name": "GMV(万元)"},
                {"type": "value", "name": "订单数"},
            ],
            "series": [
                {"name": "GMV", "type": "bar",
                 "data": [round(k["gmv"] / 10000) for k in yk],
                 "itemStyle": {"color": "#4fd1ff"}},
                {"name": "订单数", "type": "line", "yAxisIndex": 1,
                 "data": [k["orders"] for k in yk],
                 "itemStyle": {"color": "#ff7a45"}},
            ],
        }
        yhtml = f"""
        <div id="yearcmp" style="width:100%;height:320px;"></div>
        {_echarts_script()}
        <script>var c=echarts.init(document.getElementById('yearcmp'));
        c.setOption({json.dumps(yopt, ensure_ascii=False)});
        window.addEventListener('resize',()=>c.resize());</script>
        """
        components.html(yhtml, height=340, scrolling=False)

        v = rows[0]
        m = dict(zip(cols_, v))
        k1, k2, k3 = st.columns(3)
        k1.metric("总 GMV", f"{float(m['gmv'])/10000:.0f} 万元")
        k2.metric("总订单数", f"{int(float(m['orders'])):,}")
        k3.metric("客单价 AOV", f"¥{float(m['aov']):,.2f}")
        c1, c2, c3 = st.columns(3)
        c1.metric("下单用户", f"{int(float(m['user_cnt'])):,}")
        c2.metric("门店数", m["store_cnt"])
        c3.metric("退款率", f"{m['refund_rate']}%")

    # ---- 单值（省份）：数字 + 全国区域排行图并高亮该省 ----
    elif chart == "value" and rows:
        province = rows[0][0]
        val = rows[0][1]
        st.metric(f"{province}销售 GMV", f"{float(val)/10000:,.2f} 万元")
        annual = _annual_data()
        year_key = str(used_year) if used_year in YEARS else "2024"
        region_rows = annual["region"][year_key]
        region_rows = sorted(region_rows, key=lambda r: float(r["gmv"]), reverse=True)
        rlabels = [r["province"] for r in region_rows]
        rvals = [float(r["gmv"]) for r in region_rows]
        colors = ["#ff7a45" if r["province"] == province else "#4fd1ff"
                  for r in region_rows]
        st.markdown(f"##### 📊 {year_key} 年全国区域 GMV 排行（橙色为当前查询省份）")
        ropt = {
            "tooltip": {"trigger": "axis", "valueFormatter": "{c} 元"},
            "grid": {"left": 95, "right": 50, "top": 20, "bottom": 40},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": list(reversed(rlabels))},
            "series": [{"type": "bar",
                        "data": [{"value": v, "itemStyle": {"color": c}}
                                 for v, c in zip(reversed(rvals), reversed(colors))],
                        "label": {"show": True, "position": "right", "fontSize": 10}}],
        }
        rhtml = f"""
        <div id="regioncmp" style="width:100%;height:460px;"></div>
        {_echarts_script()}
        <script>var c=echarts.init(document.getElementById('regioncmp'));
        c.setOption({json.dumps(ropt, ensure_ascii=False)});
        window.addEventListener('resize',()=>c.resize());</script>
        """
        components.html(rhtml, height=480, scrolling=False)

    # ECharts 图表渲染（forecast / kpi / value 已在上方单独渲染）
    elif chart != "forecast":
        labels = [row[0] for row in display_rows]
        vals = [float(row[1]) if len(row) > 1 else 0 for row in display_rows]
        if chart == "pie":
            opt = {
                "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                "legend": {"bottom": 0, "textStyle": {"color": "#555"}},
                "series": [{"type": "pie", "radius": ["35%", "65%"],
                            "data": [{"name": l, "value": v} for l, v in zip(labels, vals)]}]
            }
        elif chart == "line":
            opt = {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 60, "right": 30, "top": 30, "bottom": 40},
                "xAxis": {"type": "category", "data": labels},
                "yAxis": {"type": "value"},
                "series": [{"type": "line", "smooth": True, "data": vals,
                            "areaStyle": {}, "itemStyle": {"color": "#4fd1ff"}}]
            }
        else:  # bar
            opt = {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 90, "right": 40, "top": 30, "bottom": 40},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": list(reversed(labels))},
                "series": [{"type": "bar", "data": list(reversed(vals)),
                            "itemStyle": {"color": "#4fd1ff", "borderRadius": [0, 4, 4, 0]}}]
            }
        html = f"""
        <div id="chart" style="width:100%;height:420px;"></div>
        {_echarts_script()}
        <script>
          var c = echarts.init(document.getElementById('chart'));
          c.setOption({json.dumps(opt, ensure_ascii=False)});
          window.addEventListener('resize', ()=>c.resize());
        </script>
        """
        components.html(html, height=440, scrolling=False)

    # 明细数据表
    with st.expander("📋 查看查询结果数据表"):
        if chart == "forecast":
            detail_cols = ["日期", "实际 GMV（元）", "预测 GMV（元）"]
        else:
            detail_cols = list(cols_)
        st.dataframe(pd.DataFrame(display_rows, columns=detail_cols),
                     use_container_width=True)

else:
    st.info("👆 请在上方输入问题，或点击示例问题快捷按钮开始查询。")
    st.markdown("""
    ### 支持的问题类型（全部年份 2022-2026）
    - **年份筛选**：顶部选择查询年份，或问题里写“2025年”“23年”“去年”
    - **总体指标**：2024年总体GMV、核心指标、经营总览
    - **趋势分析**：2025年销售趋势、各月 GMV
    - **排行分析**：2023年品类排行、2024年门店 Top10
    - **结构分析**：支付方式占比、区域销售
    - **单值查询**：2024年浙江省销售额是多少
    - **趋势预测**：输入天数自动输出每天预测值，可按年份检索预测结果；
      如“预测未来30天GMV”“2024年预测14天”，也可在界面选基准年份与天数
    """)

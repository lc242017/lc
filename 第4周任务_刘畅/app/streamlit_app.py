# -*- coding: utf-8 -*-
"""
云购生活 · 智能经营问答（Streamlit）
手册步骤4：NL2SQL 后端 + ECharts 渲染的对话闭环
运行：streamlit run streamlit_app.py
"""
import json
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from nl2sql import answer, extract_days


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


st.set_page_config(page_title="云购生活·智能经营问答", page_icon="💬", layout="wide")

st.title("💬 云购生活 · 智能经营问答")
st.caption("基于 ADS 指标层的 NL2SQL 对话应用 · 输入经营问题，自动生成 SQL 并渲染图表")

# 示例问题快捷按钮
examples = ["总体GMV是多少", "月度销售趋势", "品类销售排行",
            "支付方式占比", "门店销售Top10", "预测未来7天"]

# 用 session_state 保持问题与预测天数，避免控件刷新后丢失
if "question" not in st.session_state:
    st.session_state.question = ""
if "forecast_days" not in st.session_state:
    st.session_state.forecast_days = 7

q = st.text_input("请输入你的问题，例如：广东省上月销售额是多少？",
                  value=st.session_state.question)
cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if cols[i].button(ex, use_container_width=True):
        q = ex
        st.session_state.question = ex

# 预测类问题：在查询前展示天数输入框，输入后自动输出对应天数的预测值
is_forecast_q = bool(q and re.search(r"预测|预估|预计|forecast|未来\s*\d{1,3}\s*天", q, re.I))
if q and st.session_state.get("_last_q") != q:
    # 问题变化时，优先采用问题文本里写的天数（如“预测未来30天”）
    st.session_state.forecast_days = extract_days(q, 7)
    st.session_state._last_q = q
forecast_days = st.session_state.forecast_days
if is_forecast_q:
    fc1, fc2 = st.columns([1, 3])
    with fc1:
        forecast_days = st.number_input(
            "预测未来天数（天）", min_value=1, max_value=365, step=1,
            key="forecast_days",
            help="输入天数后自动输出未来每天的预测 GMV")
    with fc2:
        st.caption("🚀 修改天数即自动重新预测，无需手动填写数值；"
                   "也可以直接在问题里写“预测未来30天”。")

if q:
    st.session_state.question = q
    with st.spinner("正在解析问题并查询 ADS 指标层 ..."):
        r = answer(q, future_days=forecast_days if is_forecast_q else None)

    st.markdown(f"**你的问题**：{r['question']}")

    with st.expander("🔍 查看自动生成的 SQL", expanded=True):
        st.code(r["sql"], language="sql")

    st.subheader(f"📊 {r['title']}")

    chart = r["chart"]
    cols_, rows = r["columns"], r["rows"]
    display_rows = rows

    # ---- 预测：第3周手册步骤3的标准预测建模 ----
    model = r.get("model")
    if chart == "forecast" and model and "error" not in model:
        st.caption(f"📈 数据源：{model['data_source']} · "
                   f"训练 {model['train_days']} 天 / 测试 {model['test_days']} 天 "
                   f"({model['test_range'][0]} ~ {model['test_range'][1]})")

        # 模型评估指标卡 + 基线对比
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

        # 预测 vs 真实对比图（测试集 14 天）
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

        # 未来预测（历史末尾 + 未来 N 天连线）
        hist = model["history"][-30:]
        fut = model["future_rows"]
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

        # ★ 输入天数 → 自动输出每天预测值
        st.markdown(f"##### 🔮 未来 {len(fut)} 天预测值（自动输出）")
        f1, f2, f3 = st.columns(3)
        f1.metric("日均预测 GMV", f"{model['future_avg']:,.2f} 元")
        f2.metric("区间累计 GMV", f"{sum(x['pred'] for x in fut):,.2f} 元")
        f3.metric("预测区间", f"{fut[0]['date']} ~ {fut[-1]['date']}")
        st.dataframe(
            [[x["date"],
              "周末" if x["is_weekend"] else "工作日",
              "会员日" if x["is_promo"] else "普通日",
              f"{x['pred']:,.2f}"] for x in fut],
            headers=["日期", "星期类型", "营销类型", "预测 GMV（元）"],
            use_container_width=True)
        st.caption("预测值由 lag1/ma7 + 周末/会员日特征线性回归滚动生成，"
                   "修改上方“预测未来天数”即自动重算。趋势参考，遇大促/节假日需人工修正。")

        # 模型边界说明（手册要求：批判性看待模型精度）
        with st.expander("⚠️ 模型适用边界与评估说明", expanded=False):
            seg = model["segments"]
            st.markdown(f"""
            - **评估口径**：末 {model['test_days']} 天作测试集，训练集 {model['train_days']} 天，
              特征为 {', '.join(model['features'])}。
            - **精度**：MAE {m['MAE']:,.0f} 元 / MAPE {m['MAPE(%)']:.2f}%。
              ma7 移动平均基线 MAPE {model['baseline_ma7']['MAPE(%)']:.2f}%，
              模型与其接近——简单基线已具竞争力，复杂模型未显著胜出属正常现象。
            - **分段表现**：普通日 MAPE {seg['普通日']['MAPE(%)']:.2f}%、
              周末 {seg['周末']['MAPE(%)']:.2f}%、
              会员日/大促 {seg['会员日/大促']['MAPE(%)']:.2f}%。
              数据窗口仅 1 年，无去年同期，**同比不可行**，以移动平均 + 分段评估替代。
            - **外推风险**：线性回归对突变（大促、节假日、异常流量）响应滞后，
              预测值仅供趋势参考，落地需业务人工复核。
            """)

        # 明细表改展示模型对比结果
        display_rows = [[x["date"], f"{x['actual']:.2f}", f"{x['pred']:.2f}"]
                        for x in ac_rows]

    # KPI 卡片
    if chart == "kpi" and rows:
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

    # 单值
    elif chart == "value" and rows:
        for c, val in zip(cols_, rows[0]):
            st.metric(c, f"{float(val)/10000:,.2f} 万元" if c == "gmv" else val)

    # ECharts 图表渲染（forecast 已在上方单独渲染，此处跳过）
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
        elif chart == "forecast":
            # 实线=历史实际，虚线=手动输入预测，连接点重叠保证连续
            actual = [round(float(row[1]) / 10000, 2) for row in display_rows if row[2] == "实际"]
            pred = [round(float(row[1]) / 10000, 2) for row in display_rows if row[2] == "预测"]
            pred_labels = [row[0] for row in display_rows if row[2] == "预测"]
            actual_series = actual + [None] * len(pred)
            pred_series = [None] * (len(actual) - 1) + [actual[-1]] + pred
            mark = {"symbolSize": 42,
                    "data": [{"coord": [pred_labels[0], pred[-1]], "value": "预测"}]} if pred else None
            opt = {
                "tooltip": {"trigger": "axis", "valueFormatter": "{c} 万元"},
                "legend": {"data": ["历史实际", "手动预测"], "bottom": 0,
                           "textStyle": {"color": "#555"}},
                "grid": {"left": 55, "right": 30, "top": 30, "bottom": 55},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"interval": 1}},
                "yAxis": {"type": "value", "scale": True, "name": "万元"},
                "series": [
                    {"name": "历史实际", "type": "line", "smooth": True, "data": actual_series,
                     "areaStyle": {"opacity": 0.15}, "itemStyle": {"color": "#4fd1ff"}},
                    {"name": "手动预测", "type": "line", "smooth": True, "data": pred_series,
                     "lineStyle": {"type": "dashed", "width": 2}, "itemStyle": {"color": "#ff7a45"},
                     "markPoint": mark}
                ]
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
        st.dataframe(display_rows, use_container_width=True)

else:
    st.info("👆 请在上方输入问题，或点击示例问题快捷按钮开始查询。")
    st.markdown("""
    ### 支持的问题类型
    - **总体指标**：总体 GMV、核心指标、经营总览
    - **趋势分析**：月度销售趋势、各月 GMV
    - **排行分析**：品类销售排行、门店 Top10
    - **结构分析**：支付方式占比、区域销售
    - **单值查询**：浙江省销售额是多少
    - **趋势预测**：输入天数即自动输出对应天数每天预测值，例如“预测未来30天”；
      或点击快捷按钮后修改“预测未来天数”。第3周手册标准：lag1/ma7 特征 + 线性回归 + MAE/MAPE 评估 + 基线对比
    """)

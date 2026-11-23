# -*- coding: utf-8 -*-
"""
云购生活 · 智能经营问答（Streamlit）
手册步骤4：NL2SQL 后端 + ECharts 渲染的对话闭环
运行：streamlit run streamlit_app.py
"""
import json
import streamlit as st
import streamlit.components.v1 as components
from nl2sql import answer

st.set_page_config(page_title="云购生活·智能经营问答", page_icon="💬", layout="wide")

st.title("💬 云购生活 · 智能经营问答")
st.caption("基于 ADS 指标层的 NL2SQL 对话应用 · 输入经营问题，自动生成 SQL 并渲染图表")

# 示例问题快捷按钮
examples = ["总体GMV是多少", "月度销售趋势", "品类销售排行",
            "支付方式占比", "门店销售Top10", "浙江省销售额是多少"]
q = st.text_input("请输入你的问题，例如：广东省上月销售额是多少？", value="")
cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if cols[i].button(ex, use_container_width=True):
        q = ex

if q:
    with st.spinner("正在解析问题并查询 ADS 指标层 ..."):
        r = answer(q)

    st.markdown(f"**你的问题**：{r['question']}")

    with st.expander("🔍 查看自动生成的 SQL", expanded=True):
        st.code(r["sql"], language="sql")

    st.subheader(f"📊 {r['title']}")

    chart = r["chart"]
    cols_, rows = r["columns"], r["rows"]

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

    # ECharts 图表渲染
    else:
        labels = [row[0] for row in rows]
        vals = [float(row[1]) if len(row) > 1 else 0 for row in rows]
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
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <script>
          var c = echarts.init(document.getElementById('chart'));
          c.setOption({json.dumps(opt, ensure_ascii=False)});
          window.addEventListener('resize', ()=>c.resize());
        </script>
        """
        components.html(html, height=440, scrolling=False)

    # 明细数据表
    with st.expander("📋 查看查询结果数据表"):
        st.dataframe(rows, use_container_width=True)

else:
    st.info("👆 请在上方输入问题，或点击示例问题快捷按钮开始查询。")
    st.markdown("""
    ### 支持的问题类型
    - **总体指标**：总体 GMV、核心指标、经营总览
    - **趋势分析**：月度销售趋势、各月 GMV
    - **排行分析**：品类销售排行、门店 Top10
    - **结构分析**：支付方式占比、区域销售
    - **单值查询**：浙江省销售额是多少
    """)

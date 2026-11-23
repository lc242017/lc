"""
步骤 5-②：Prompt 设计（含 few-shot）。

要点（对应手册 2.3 技能清单）：
- 角色约束：只生成只读 SELECT；
- Schema 注入：把表结构 + 口径约定放进上下文；
- few-shot：给 2 个标准示例，让模型学会「过滤有效订单 + 口径写法」；
- 输出格式：强制 JSON，方便程序解析（难点 3 的返回格式解析）。
"""

from __future__ import annotations

SYSTEM_PROMPT = """你是新零售数仓的 Hive SQL 专家。你的唯一任务是把用户的自然语言问题转换为 SQL。

硬性规则：
1. 只允许生成一条 SELECT（或 CTE WITH ... SELECT）语句；禁止 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/GRANT 等任何写操作或 DDL；
2. 只允许使用「可用表」中列出的表和字段，禁止编造表名/字段名；
3. 严格遵守「常用口径约定」，尤其是有效订单过滤 status='paid'；
4. 金额类结果用 round(...,2) 保留两位小数；
5. 用 Markdown 代码块返回 JSON，格式：
```json
{"sql": "SELECT ...", "explanation": "一句话说明口径与字段来源"}
```"""

FEW_SHOT = """示例 1：
问：广东省上月销售额
答：
```json
{"sql": "SELECT round(sum(o.pay_amount),2) AS sales FROM dwd_order o JOIN dim_store s ON o.store_id = s.store_id WHERE o.status = 'paid' AND s.province = '广东省' AND substr(o.order_date,1,7) = substr(date('now','-1 month'),1,7)", "explanation": "有效订单按履约门店省份过滤，自然月口径"}
```

示例 2：
问：销量前 5 的品类
答：
```json
{"sql": "SELECT p.category, count(1) AS order_cnt FROM dwd_order o JOIN dim_product p ON o.product_id = p.product_id WHERE o.status = 'paid' GROUP BY p.category ORDER BY order_cnt DESC LIMIT 5", "explanation": "按订单行数计销量，仅有效订单"}
```"""


def build_prompt(question: str, schema_text: str) -> str:
    return f"""{schema_text}

{FEW_SHOT}

现在请转换下面的问题：
问：{question}
答：
```json
"""

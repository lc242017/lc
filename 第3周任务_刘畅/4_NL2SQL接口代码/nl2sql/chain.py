"""
步骤 5-③：NL2SQL 链路。

链路：Schema 抽取 → Prompt 组装 → 大模型生成 SQL → SQL 白名单校验 → 本地执行 → 结果。

安全设计（对应难点 3「大模型 SQL 不可控」）：
- 模型输出先过 SQLGuard：只允许单条 SELECT/WITH，命中写操作/DDL/PRAGMA/多语句直接拒绝；
- 拒绝不重试执行，返回结构化错误给调用方；
- 执行加 timeout 与行数上限，防全表扫描拖死环境。

LangChain 集成：提供 `langchain_adapter`，若环境安装了 langchain-openai，
可用 LangChainPromptTemplate + LCEL 串联同一条链；未安装时走内置实现，逻辑完全一致。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm.client import LLMClient, get_env  # noqa: E402
from nl2sql.prompts import SYSTEM_PROMPT, build_prompt  # noqa: E402
from nl2sql.schema import schema_desc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "yunmall.db"
MAX_ROWS = 200
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|grant|revoke|"
    r"attach|detach|pragma|vacuum|explain|merge|load|call)\b",
    re.I,
)


@dataclass
class NL2SQLResult:
    question: str
    sql: str
    explanation: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    source: str = ""          # online / offline-mock / retry
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "sql": self.sql,
            "explanation": self.explanation,
            "columns": self.columns,
            "rows": self.rows[:20],
            "row_count": len(self.rows),
            "source": self.source,
            "error": self.error,
        }


class SQLGuard:
    """模型生成 SQL 的白名单校验。"""

    @staticmethod
    def validate(sql: str) -> tuple[bool, str]:
        s = sql.strip().rstrip(";")
        if not s:
            return False, "SQL 为空"
        if ";" in s:
            return False, "拒绝：包含多条语句"
        if FORBIDDEN.search(s):
            return False, "拒绝：包含非只读关键字（INSERT/UPDATE/DELETE/DDL 等）"
        first = re.split(r"\s+", s, maxsplit=1)[0].lower()
        if first not in ("select", "with"):
            return False, f"拒绝：语句必须以 SELECT/WITH 开头，实际是 {first!r}"
        return True, "ok"


def execute_sql(sql: str) -> tuple[list[str], list[list]]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("pragma query_only = on")   # 连接级只读，双保险
    cur = conn.execute(sql)
    columns = [d[0] for d in cur.description] if cur.description else []
    rows = [list(map(lambda v: round(v, 2) if isinstance(v, float) else v, r))
            for r in cur.fetchmany(MAX_ROWS + 1)][:MAX_ROWS]
    conn.close()
    return columns, rows


# ---------------------------------------------------------------------------
# 离线模板引擎：无 API Key 时的兜底「模型」。
# 位置在 client 之外，是因为它模拟的是 NL2SQL 任务的输出格式，而不是通用对话。
# ---------------------------------------------------------------------------
_MOCK_RULES = [
    (r"广东省.*上月|上月.*广东省", "SELECT round(sum(o.pay_amount),2) AS sales FROM dwd_order o JOIN dim_store s ON o.store_id=s.store_id WHERE o.status='paid' AND s.province='广东省' AND substr(o.order_date,1,7)=substr(date('now','-1 month'),1,7)"),
    (r"销量.{0,3}前\s*5|前\s*5.{0,3}销量", "SELECT p.category, count(1) AS order_cnt FROM dwd_order o JOIN dim_product p ON o.product_id=p.product_id WHERE o.status='paid' GROUP BY p.category ORDER BY order_cnt DESC LIMIT 5"),
    (r"销售额.{0,4}前\s*5|前\s*5.{0,3}品类", "SELECT p.category, round(sum(o.pay_amount),2) AS sales FROM dwd_order o JOIN dim_product p ON o.product_id=p.product_id WHERE o.status='paid' GROUP BY p.category ORDER BY sales DESC LIMIT 5"),
    (r"最近\s*7\s*天.{0,6}(GMV|销售额)|每日\s*GMV", "SELECT order_date, gmv, orders, aov FROM ads_kpi_day ORDER BY order_date DESC LIMIT 7"),
    (r"客单价.{0,10}(最高|top|Top)", "SELECT s.store_name, round(sum(o.pay_amount)*1.0/count(distinct o.order_id),2) AS aov FROM dwd_order o JOIN dim_store s ON o.store_id=s.store_id WHERE o.status='paid' GROUP BY s.store_name ORDER BY aov DESC LIMIT 3"),
    (r"(月度|每月|分月).{0,4}复购率", "SELECT month, buyers, repeat_users, repurchase_rate FROM ads_repurchase_month ORDER BY month"),
    (r"复购率", "SELECT round(count(distinct case when cnt>=2 then user_id end)*1.0/count(distinct user_id),4) AS repurchase_rate FROM (SELECT user_id, count(distinct order_id) AS cnt FROM dwd_order WHERE status='paid' GROUP BY user_id)"),
    (r"(月度|每月).*(GMV|销售额)|分月", "SELECT substr(order_date,1,7) AS month, round(sum(pay_amount),2) AS gmv FROM dwd_order WHERE status='paid' GROUP BY substr(order_date,1,7) ORDER BY month"),
    (r"门店.*(排行|排名|top)|top\s*10.*门店", "SELECT s.store_name, round(sum(o.pay_amount),2) AS gmv FROM dwd_order o JOIN dim_store s ON o.store_id=s.store_id WHERE o.status='paid' GROUP BY s.store_name ORDER BY gmv DESC LIMIT 10"),
]


def mock_llm(user_prompt: str) -> str:
    """从 user_prompt 中抽出问题文本，按规则模板返回与真实模型相同的 JSON 格式。"""
    m = re.search(r"现在请转换下面的问题：\s*问：(.+?)\n答：", user_prompt, re.S)
    question = m.group(1).strip() if m else user_prompt
    for pattern, sql in _MOCK_RULES:
        if re.search(pattern, question):
            body = json.dumps({"sql": sql, "explanation": "offline-mock 模板生成（未调用真实大模型）"},
                              ensure_ascii=False, indent=2)
            return f"```json\n{body}\n```"
    return "无法识别该问题，请换一个示例问题。"


class NL2SQLChain:
    def __init__(self, client: LLMClient | None = None):
        self.client = client or LLMClient()
        self.schema_text = schema_desc()

    def run(self, question: str) -> NL2SQLResult:
        prompt = build_prompt(question, self.schema_text)
        reply = self.client.chat(SYSTEM_PROMPT, prompt, mock_fn=mock_llm)
        try:
            parsed = LLMClient.parse_sql_reply(reply.content)
        except ValueError as exc:
            return NL2SQLResult(question, sql="", source=reply.mode, error=str(exc))

        ok, msg = SQLGuard.validate(parsed["sql"])
        if not ok:
            return NL2SQLResult(question, sql=parsed["sql"], source=reply.mode, error=msg)

        try:
            columns, rows = execute_sql(parsed["sql"])
        except Exception as exc:  # noqa: BLE001
            return NL2SQLResult(question, sql=parsed["sql"], source=reply.mode,
                                error=f"SQL 执行失败：{exc}")
        return NL2SQLResult(question, sql=parsed["sql"], explanation=parsed.get("explanation", ""),
                            columns=columns, rows=rows, source=reply.mode)


def langchain_adapter(question: str) -> NL2SQLResult:
    """可选：用 LangChain LCEL 串联同一条链（需 pip install langchain langchain-openai）。
    这里保持与 NL2SQLChain 相同的 Prompt / 校验 / 执行，方便对比两套写法。"""
    try:
        from langchain_core.messages import SystemMessage
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 langchain，请使用 NL2SQLChain，或 pip install langchain langchain-openai") from exc

    llm = ChatOpenAI(
        model=get_env("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=get_env("DEEPSEEK_API_KEY", ""),
        base_url=get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
    )
    # 注意：SYSTEM_PROMPT 内含 JSON 花括号，必须用静态 SystemMessage 传入，
    # 否则 ChatPromptTemplate 会把 {"sql": ...} 当成模板变量而报 KeyError。
    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=SYSTEM_PROMPT), ("human", "{user_prompt}")]
    )
    chain = prompt | llm | StrOutputParser()
    content = chain.invoke({"user_prompt": build_prompt(question, schema_desc())})
    parsed = LLMClient.parse_sql_reply(content)
    ok, msg = SQLGuard.validate(parsed["sql"])
    if not ok:
        return NL2SQLResult(question, sql=parsed["sql"], source="langchain", error=msg)
    columns, rows = execute_sql(parsed["sql"])
    return NL2SQLResult(question, sql=parsed["sql"], explanation=parsed.get("explanation", ""),
                        columns=columns, rows=rows, source="langchain")

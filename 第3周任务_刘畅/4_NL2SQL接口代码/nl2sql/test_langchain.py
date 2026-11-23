"""
步骤 5 补充验收：LangChain 链路自检。

只验证「链可构建 + Prompt 渲染正确」，不发起真实网络请求（无 Key 环境也能跑）。
配置 DEEPSEEK_API_KEY 后可用 --invoke 走一次真实生成。

用法：
    python nl2sql/test_langchain.py            # 结构自检
    python nl2sql/test_langchain.py --invoke   # 真实调用（需 Key）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm.client import get_env  # noqa: E402
from nl2sql.chain import SQLGuard, execute_sql  # noqa: E402
from nl2sql.prompts import SYSTEM_PROMPT, build_prompt  # noqa: E402
from nl2sql.schema import schema_desc  # noqa: E402


def main() -> int:
    try:
        import importlib.metadata as md

        from langchain_core.messages import SystemMessage
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        print(f"[FAIL] LangChain 未安装：{exc}")
        return 1

    print(f"[1] 版本：langchain-core={md.version('langchain-core')} "
          f"langchain-openai={md.version('langchain-openai')}")

    llm = ChatOpenAI(
        model=get_env("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=get_env("DEEPSEEK_API_KEY", "") or "sk-structure-check-only",
        base_url=get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
    )
    # 静态 SystemMessage：SYSTEM_PROMPT 中的 JSON 花括号不能被当作模板变量
    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=SYSTEM_PROMPT), ("human", "{user_prompt}")]
    )
    chain = prompt | llm | StrOutputParser()
    print("[2] 链构建成功：ChatPromptTemplate | ChatOpenAI | StrOutputParser")

    msgs = chain.steps[0].format_messages(
        user_prompt=build_prompt("销量前 5 的品类", schema_desc())
    )
    system_text, human_text = msgs[0].content, msgs[1].content
    assert "只允许生成一条 SELECT" in system_text, "系统提示缺失安全约束"
    assert "dwd_order" in human_text and "dim_product" in human_text, "Schema 未注入 Prompt"
    assert "示例 1" in human_text and "示例 2" in human_text, "few-shot 未注入"
    print(f"[3] Prompt 渲染正确：system {len(system_text)} 字 / human {len(human_text)} 字"
          f"（含 Schema + 2 个 few-shot 示例）")

    # 与主链路共用同一套校验与执行器，保证两套写法行为一致
    demo_sql = ("SELECT p.category, round(sum(o.pay_amount),2) AS sales "
                "FROM dwd_order o JOIN dim_product p ON o.product_id=p.product_id "
                "WHERE o.status='paid' GROUP BY p.category ORDER BY sales DESC LIMIT 5")
    ok, msg = SQLGuard.validate(demo_sql)
    cols, rows = execute_sql(demo_sql)
    print(f"[4] 共用 SQLGuard/执行器：校验={msg}，返回 {len(rows)} 行，列={cols}")

    blocked, bmsg = SQLGuard.validate("DROP TABLE dwd_order")
    print(f"[5] 危险语句拦截：{'DROP TABLE dwd_order'!r} -> {bmsg}")
    assert not blocked

    if "--invoke" in sys.argv:
        if not get_env("DEEPSEEK_API_KEY"):
            print("[WARN] 未配置 DEEPSEEK_API_KEY，跳过真实调用")
        else:
            out = chain.invoke({"user_prompt": build_prompt("销量前 5 的品类", schema_desc())})
            print(f"[6] 真实调用返回：{out[:200]}...")

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

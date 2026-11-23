"""
步骤 5 验收脚本：NL2SQL 示例问答跑通，并把演示记录落盘。

用法：python nl2sql/cli.py
产物：output/nl2sql_demo.md / output/nl2sql_demo.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nl2sql.chain import NL2SQLChain  # noqa: E402

OUT_DIR = ROOT / "output"
DEMO_QUESTIONS = [
    "广东省上月销售额是多少",
    "销量前 5 的品类",
    "最近 7 天每日 GMV",
    "客单价最高的前 3 个门店",
    "近半年的月度复购率",
]


def render_md(results) -> str:
    lines = ["# NL2SQL 演示记录", "",
             f"生成时间：2026-11-10　|　模式：{results[0].source}", ""]
    for r in results:
        lines += [f"## 问：{r.question}", ""]
        if r.error:
            lines += [f"**[拒绝/失败]** {r.error}", "", f"原始 SQL：`{r.sql}`", ""]
            continue
        lines += [
            "**生成 SQL：**", "", "```sql", r.sql, "```", "",
            f"口径说明：{r.explanation or '-'}", "",
            f"**返回 {len(r.rows)} 行：**", "",
            "| " + " | ".join(r.columns) + " |",
            "| " + " | ".join(["---"] * len(r.columns)) + " |",
        ]
        for row in r.rows[:10]:
            lines.append("| " + " | ".join(str(v) for v in row) + " |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    chain = NL2SQLChain()
    results = []
    for q in DEMO_QUESTIONS:
        r = chain.run(q)
        results.append(r)
        print(f"\n问：{q}")
        print(f"  模式：{r.source}")
        print(f"  SQL：{r.sql}")
        if r.error:
            print(f"  [拒绝] {r.error}")
            continue
        print(f"  结果（{len(r.rows)} 行）：")
        for row in r.rows[:5]:
            print(f"    {row}")

    os.makedirs(OUT_DIR, exist_ok=True)
    (OUT_DIR / "nl2sql_demo.md").write_text(render_md(results), encoding="utf-8")
    (OUT_DIR / "nl2sql_demo.json").write_text(
        json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OUT] {OUT_DIR / 'nl2sql_demo.md'}")
    print(f"[OUT] {OUT_DIR / 'nl2sql_demo.json'}")


if __name__ == "__main__":
    main()

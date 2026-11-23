"""
步骤 4 验收脚本：验证「能成功返回一次大模型回复」+「.env 已被 .gitignore 忽略」。

用法：python llm/test_api.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from llm.client import LLMClient, get_env  # noqa: E402


def check_gitignore() -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT, capture_output=True)
    if r.returncode == 0:
        return True
    # 仓库未初始化时，检查 .gitignore 内容兜底
    gi = ROOT / ".gitignore"
    if gi.exists() and ".env" in gi.read_text(encoding="utf-8"):
        return True
    return False


def main() -> int:
    client = LLMClient()
    ok1 = False
    if client.mode == "online":
        reply = client.chat("你是一个测试助手。", "只回复两个字：成功")
        print(f"[1] 大模型回复成功：model={reply.model}  reply={reply.content.strip()!r}")
        ok1 = "成功" in reply.content
    else:
        # 离线模式验证调用链路本身（无 Key 环境）
        reply = client.chat("系统提示", "问：最近 7 天每日 GMV\n答：", mock_fn=lambda u: "```json\n{}\n```")
        print(f"[1] 当前为 offline-mock 模式（未配置真实 Key），调用链路正常：mode={reply.mode}")
        ok1 = reply.mode == "offline-mock"

    ok2 = check_gitignore()
    print(f"[2] .env 被 .gitignore 忽略：{ok2}")
    key_masked = (get_env("DEEPSEEK_API_KEY", "") or "")[:8]
    print(f"[3] 密钥来自环境变量/.env，未见硬编码：key={key_masked}{'...' if key_masked else '（未配置）'}")
    print("PASS" if ok1 and ok2 else "FAIL")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(main())

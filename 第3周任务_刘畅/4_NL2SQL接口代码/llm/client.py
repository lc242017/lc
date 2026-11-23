"""
步骤 4：大模型 API 接入与密钥管理。

密钥安全约定（对应手册难点 4）：
- API Key 一律放项目根目录 `.env`（该文件已在 .gitignore 中，绝不入库）；
- 代码里只出现 `os.environ["DEEPSEEK_API_KEY"]`，无任何硬编码密钥；
- `.env.example` 提供模板，团队成员各自复制填写。

调用约定（对应手册难点 3：最小化调用、返回格式解析）：
- 仅在需要生成 SQL 时调用一次 chat.completions，temperature=0（可复现）；
- 返回解析统一收敛到 JSON：{"sql": "...", "explanation": "..."}；
- 未配置 Key 时进入 offline-mock 模式（模板引擎），保证教学链路可跑通。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env(path: Path = ENV_PATH) -> dict:
    """极简 .env 解析（避免强制依赖 python-dotenv）。已存在的环境变量优先。"""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


_ENV = load_env()


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key) or _ENV.get(key) or default


@dataclass
class LLMReply:
    content: str        # 模型原始回复
    mode: str           # online（真实 API） / offline-mock
    model: str


class LLMClient:
    """统一的大模型调用入口。线上走 OpenAI 兼容协议（DeepSeek），离线走模板引擎。"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or get_env("DEEPSEEK_API_KEY", "").strip()
        self.base_url = base_url or get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or get_env("DEEPSEEK_MODEL", "deepseek-chat")
        self.mode = "online" if self.api_key and not self.api_key.startswith("sk-xxxx") else "offline-mock"
        self._client = None
        if self.mode == "online":
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError as exc:
                raise RuntimeError("已配置 API Key 但未安装 openai SDK：pip install openai") from exc

    # ------------------------------------------------------------------
    def chat(self, system: str, user: str, temperature: float = 0.0,
             mock_fn=None) -> LLMReply:
        """一次最小化调用。offline-mock 模式用 mock_fn(question) 生成同格式回复。"""
        if self.mode == "online":
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=1024,
            )
            return LLMReply(resp.choices[0].message.content, mode="online", model=self.model)
        if mock_fn is None:
            raise RuntimeError("offline-mock 模式需要提供 mock_fn")
        return LLMReply(mock_fn(user), mode="offline-mock", model="template-engine")

    # ------------------------------------------------------------------
    @staticmethod
    def parse_sql_reply(content: str) -> dict:
        """解析模型回复：优先取 ```json，再退化到 ```sql / 裸文本提取。"""
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                if "sql" in data:
                    return {"sql": str(data["sql"]).strip(), "explanation": str(data.get("explanation", ""))}
            except json.JSONDecodeError:
                pass
        m = re.search(r"```sql\s*(.*?)\s*```", content, re.S)
        if m:
            return {"sql": m.group(1).strip(), "explanation": "（模型以 sql 代码块返回）"}
        # 裸文本兜底：抓第一条以 select/with 开头的语句
        m = re.search(r"((?:with|select)\b.+?)(?:;|$)", content, re.S | re.I)
        if m:
            return {"sql": m.group(1).strip(), "explanation": "（从回复文本中提取）"}
        raise ValueError(f"无法从模型回复中解析出 SQL：{content[:200]!r}")


if __name__ == "__main__":
    client = LLMClient()
    print(f"mode = {client.mode}")
    if client.mode == "online":
        resp = client.chat("你是助手。", "回复两个字：成功")
        print(f"model = {resp.model}")
        print(f"reply = {resp.content!r}")
    else:
        print("未检测到有效 DEEPSEEK_API_KEY，当前为离线模板模式；"
              "复制 .env.example 为 .env 并填入真实 Key 后即为在线模式。")

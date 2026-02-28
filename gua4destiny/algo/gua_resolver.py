import os
from typing import Any, List, Optional, Iterator

import dotenv

from openai import OpenAI

try:
    from .gua_model import Gua
    from .gua_types import YinYang, YinYangType, YaoType

except ImportError:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    from gua4destiny.algo.gua_model import Gua
    from gua4destiny.algo.gua_types import YinYang, YinYangType, YaoType


def extract_response_text(resp: Any) -> str:
    """从 OpenAI Responses 对象或字典中提取可读文本。

    兼容常见结构：resp.output(s) -> list -> content -> text
    回退到顶层的 `text` / `output_text` / `response` 字段，最后回退到 str(resp)。
    """
    if isinstance(resp, dict):
        outputs = resp.get("output") or resp.get("outputs")
    else:
        outputs = getattr(resp, "output", None) or getattr(resp, "outputs", None)

    texts: List[str] = []
    if outputs:
        for out in outputs:
            contents = out.get("content") if isinstance(out, dict) else getattr(out, "content", None)
            if not contents:
                continue
            for c in contents:
                if isinstance(c, dict):
                    t = c.get("text") or c.get("content")
                else:
                    t = getattr(c, "text", None)
                if t:
                    texts.append(t)

    if texts:
        return "\n\n".join(texts)

    # 回退到常见顶层字段
    if isinstance(resp, dict):
        for k in ("text", "output_text", "response"):
            if k in resp and isinstance(resp[k], str):
                return resp[k]
    else:
        for k in ("text", "output_text"):
            if hasattr(resp, k):
                val = getattr(resp, k)
                if isinstance(val, str):
                    return val

    return str(resp)


def _extract_text_from_event(event: Any) -> Optional[str]:
    """从流事件中提取增量文本（若存在）。"""
    if event is None:
        return None

    # dict 风格事件（例如 chunk dict）
    if isinstance(event, dict):
        # choices -> delta -> content/text
        choices = event.get("choices")
        if isinstance(choices, list) and choices:
            for choice in choices:
                if isinstance(choice, dict):
                    delta = choice.get("delta")
                    if isinstance(delta, dict):
                        cont = delta.get("content") or delta.get("text")
                        if isinstance(cont, str):
                            return cont
                        if isinstance(cont, dict):
                            t = cont.get("text") or cont.get("content")
                            if isinstance(t, str):
                                return t

        # 直接 delta 字段
        delta = event.get("delta")
        if isinstance(delta, dict):
            for k in ("content", "text"):
                v = delta.get(k)
                if isinstance(v, str):
                    return v

        # content / outputs 数组
        content = event.get("content") or event.get("outputs")
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    t = item.get("text") or item.get("content")
                    if isinstance(t, str):
                        parts.append(t)
            if parts:
                return "".join(parts)

        # 顶层回退
        for k in ("text", "output_text", "message"):
            if k in event and isinstance(event[k], str):
                return event[k]
        return None

    # 对象风格事件（例如 chunk 对象）
    if hasattr(event, "choices"):
        choices = getattr(event, "choices")
        if isinstance(choices, list):
            for choice in choices:
                delta = getattr(choice, "delta", None)
                if delta is not None:
                    cont = getattr(delta, "content", None) or getattr(delta, "text", None)
                    if isinstance(cont, str):
                        return cont
                    if isinstance(cont, dict):
                        t = cont.get("text") if isinstance(cont, dict) else None
                        if isinstance(t, str):
                            return t

    for attr in ("delta", "content", "text", "output_text"):
        if hasattr(event, attr):
            val = getattr(event, attr)
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                parts = []
                for it in val:
                    if isinstance(it, dict):
                        t = it.get("text") or it.get("content")
                        if isinstance(t, str):
                            parts.append(t)
                    elif hasattr(it, "text"):
                        t = getattr(it, "text")
                        if isinstance(t, str):
                            parts.append(t)
                if parts:
                    return "".join(parts)
    return None


class GuaResolver:
    """封装卦象解析的可复用解析器。

    不再支持注入本地客户端，始终从环境变量创建 `OpenAI` 客户端实例。
    """

    def __init__(self, *, default_model: Optional[str] = None, system_role: Optional[str] = None):
        dotenv.load_dotenv()

        self.client = OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_KEY"),
        )
        self.default_model = default_model or os.getenv("OPENAI_MODEL", "gpt-4-0613")
        self.system_role = system_role or "你是一个精通周易的占卜师。"

    def build_prompt(self, question: str, gua: Gua) -> str:
        """构建发送给模型的提示语，单独抽取便于复用和单元测试。"""
        return f"请根据以下卦象信息解析问题：\n\n问题: {question}\n卦象: {gua.name}\n全文: {gua.get_full_text()}\n\n请提供详细的解析结果。"

    def resolve_gua_raw(self, question: str, gua: Gua, model: Optional[str] = None) -> Any:
        """返回 OpenAI 原始响应对象，便于上层自定义解析流程。"""
        prompt = self.build_prompt(question, gua)
        return self.client.responses.create(
            model=model or self.default_model,
            input=[{"role": "system", "content": self.system_role}, {"role": "user", "content": prompt}],
        )

    def resolve_gua_stream(self, question: str, gua: Gua, model: Optional[str] = None) -> Iterator[str]:
        """以生成器方式流式返回解析文本片段，便于前端实时展示。

        优先尝试 `chat.completions.create(..., stream=True)`（返回 chunk 对象），
        然后回退到 `responses.stream` 或 `responses.create(..., stream=True)`。
        """
        prompt = self.build_prompt(question, gua)
        model_to_use = model or self.default_model

        # 优先尝试 chat completion 的流式接口（chunk.choices[0].delta.content）
        try:
            if hasattr(self.client, "chat") and hasattr(self.client.chat, "completions"):
                comp = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "system", "content": self.system_role}, {"role": "user", "content": prompt}],
                    stream=True,
                )
                if hasattr(comp, "__enter__"):
                    with comp as it:
                        for chunk in it:
                            text_piece = None
                            try:
                                if hasattr(chunk, "choices"):
                                    choices = getattr(chunk, "choices")
                                    if isinstance(choices, list) and choices:
                                        first = choices[0]
                                        delta = getattr(first, "delta", None)
                                        if delta is not None:
                                            content = getattr(delta, "content", None) or getattr(delta, "text", None)
                                            if isinstance(content, str):
                                                text_piece = content
                            except Exception:
                                pass
                            if text_piece is None:
                                text_piece = _extract_text_from_event(chunk)
                            if text_piece:
                                yield text_piece
                else:
                    for chunk in comp:
                        text_piece = _extract_text_from_event(chunk)
                        if text_piece:
                            yield text_piece
                return
        except Exception:
            pass

        # 次选：responses API 的 stream 或 create(..., stream=True)
        try:
            if hasattr(self.client.responses, "stream"):
                streamer = self.client.responses.stream(
                    model=model_to_use,
                    input=[{"role": "system", "content": self.system_role}, {"role": "user", "content": prompt}],
                )
            else:
                streamer = self.client.responses.create(
                    model=model_to_use,
                    input=[{"role": "system", "content": self.system_role}, {"role": "user", "content": prompt}],
                    stream=True,
                )
        except Exception:
            full = self.resolve_gua(question, gua, model=model_to_use)
            yield full
            return

        try:
            if hasattr(streamer, "__enter__"):
                with streamer as stream_iter:
                    for event in stream_iter:
                        text_piece = _extract_text_from_event(event)
                        if text_piece:
                            yield text_piece
            else:
                for event in streamer:
                    text_piece = _extract_text_from_event(event)
                    if text_piece:
                        yield text_piece
        except TypeError:
            full = extract_response_text(streamer)
            yield full

    def resolve_gua(self, question: str, gua: Gua, model: Optional[str] = None) -> str:
        """返回解析后的纯文本结果（调用 `extract_response_text`）。"""
        raw = self.resolve_gua_raw(question, gua, model=model)
        return extract_response_text(raw)

    def __call__(self, question: str, gua: Gua, model: Optional[str] = None, stream: bool = False) -> Any:
        """提供一个统一的接口，根据 `stream` 参数决定返回完整文本还是流式生成器。"""
        if stream:
            return self.resolve_gua_stream(question, gua, model=model)
        else:
            return self.resolve_gua(question, gua, model=model)


if __name__ == "__main__":
    # 示例用法（假定已正确配置 .env 中的 OPENAI_KEY）
    question = "考试成绩如何？"
    gua = Gua(
        yaos=[
            YaoType.Vieux_Lune,
            YaoType.Jeune_Soleil,
            YaoType.Jeune_Lune,
            YaoType.Vieux_Soleil,
            YaoType.Jeune_Soleil,
            YaoType.Vieux_Lune,
        ]
    )

    resolver = GuaResolver()

    print("\n--- 流式解析示例 ---")
    for piece in resolver.resolve_gua_stream(question, gua):
        if isinstance(piece, str):
            piece_text = piece
        else:
            piece_text = _extract_text_from_event(piece) or extract_response_text(piece) or str(piece)
        print(piece_text, end="", flush=True)

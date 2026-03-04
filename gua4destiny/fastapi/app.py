from __future__ import annotations

import json
import os
from typing import Generator, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from io import BytesIO
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None

from gua4destiny.algo.gua_model import Gua
from gua4destiny.algo.gua_resolver import GuaResolver, _extract_text_from_event, extract_response_text
from gua4destiny.algo.gua_types import YaoType
from gua4destiny.algo.visualize import GuaVisualizer
from .schemas import GuaInput, ResolveResponse, GenerateGuaInput, GuaResponse
from .schemas import HistoryRead, HistoryUpdate
from . import db as _db
from sqlmodel import select


app = FastAPI(title="Gua4Destiny API", version="0.1.0")

resolver = GuaResolver()


@app.on_event("startup")
def on_startup():
    try:
        _db.init_db()
    except Exception:
        pass


# 挂载前端静态文件（若存在），提供一个简单的单页前端：/ui
try:
    base_webui = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "webui"))
    if os.path.isdir(base_webui):
        app.mount("/ui", StaticFiles(directory=base_webui, html=True), name="webui")
except Exception:
    pass


def _parse_yaos(yaos: List[object]) -> List[YaoType]:
    """将前端传入的爻表示（名字或数值）转换为 `YaoType` 列表。"""
    if yaos is None:
        return None
    parsed: List[YaoType] = []
    for item in yaos:
        if isinstance(item, int):
            # 允许直接传入枚举值
            try:
                parsed.append(YaoType(item))
            except Exception as e:
                raise ValueError(f"无效的爻值: {item}")
        elif isinstance(item, str):
            # 支持枚举名称（不区分大小写）
            try:
                parsed.append(YaoType[item])
            except KeyError:
                # 尝试按整数字符串解析
                try:
                    parsed.append(YaoType(int(item)))
                except Exception:
                    raise ValueError(f"无效的爻名: {item}")
        else:
            raise ValueError(f"不支持的爻类型: {type(item)}")
    return parsed


@app.get("/", response_class=JSONResponse)
async def health():
    return {"status": "ok"}


@app.post("/api/resolve", response_model=ResolveResponse)
async def resolve(input: GuaInput):
    """同步解析：一次性返回完整解析文本。"""
    try:
        yaos = _parse_yaos(input.yaos) if input.yaos else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gua = Gua(yaos=yaos) if yaos is not None else Gua()

    text = resolver.resolve_gua(input.question, gua)
    # 保存历史记录
    try:
        session = _db.get_session()
        yaos_json = None
        if input.yaos:
            try:
                import json as _json

                yaos_json = _json.dumps(input.yaos, ensure_ascii=False)
            except Exception:
                yaos_json = None

        hist = _db.History(question=input.question, yaos_json=yaos_json, response_text=text, mode="resolve")
        session.add(hist)
        session.commit()
        session.refresh(hist)
        session.close()
    except Exception:
        pass
    return ResolveResponse(text=text)


@app.post("/api/stream")
async def stream(request: Request, input: GuaInput):
    """流式解析：以 Server-Sent Events (SSE) 的格式逐块推送文本片段。

    前端可以连接到此端点并按 SSE 协议消费实时片段。若需要 WebSocket，也可改造。
    """
    try:
        yaos = _parse_yaos(input.yaos) if input.yaos else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gua = Gua(yaos=yaos) if yaos is not None else Gua()

    async def await_client_disconnected() -> bool:
        # FastAPI/Starlette 的 Request 有 is_disconnected 方法
        try:
            return await request.is_disconnected()
        except Exception:
            return False

    async def event_generator():
        # 为流式请求先创建历史记录，随后在生成完成后更新
        session = None
        hist = None
        try:
            session = _db.get_session()
            import json as _json

            yaos_json = _json.dumps(input.yaos, ensure_ascii=False) if input.yaos else None
            hist = _db.History(question=input.question, yaos_json=yaos_json, response_text="", mode="stream")
            session.add(hist)
            session.commit()
            session.refresh(hist)
        except Exception:
            if session:
                session.close()
            session = None
        for piece in resolver.resolve_gua_stream(input.question, gua):
            # 当客户端断开连接时，停止生成
            if await await_client_disconnected():
                break
            # piece 可能是对象或 dict，需要归一成文本
            if isinstance(piece, str):
                text = piece
            else:
                text = _extract_text_from_event(piece) or extract_response_text(piece) or str(piece)
            # SSE 格式：每个 event 用 data: 开头，空行结束
            yield f"data: {json.dumps({'text': text})}\n\n"

        # 流结束后，更新历史记录的 response_text（若有 session）
        try:
            if session and hist:
                # 聚合文本：这里简单地用 resolver 再跑一遍以确保完整文本，
                # 或者也可以在循环中拼接 pieces 到变量并赋值；为简单起见读取 resolver.resolve_gua
                final_text = resolver.resolve_gua(input.question, gua)
                hist.response_text = final_text
                session.add(hist)
                session.commit()
                session.close()
        except Exception:
            try:
                if session:
                    session.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/image")
async def image(input: GenerateGuaInput, format: str = "png"):
    """返回当前卦的图片。

    参数 `format` 支持 `png`（默认）或 `svg`。当 `format=svg` 时直接返回 SVG 文本，
    否则按现有逻辑生成 PNG（优先使用 cairosvg，回退到 Pillow）。
    """
    try:
        yaos = _parse_yaos(input.yaos) if input.yaos else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gua = Gua(yaos=yaos) if yaos is not None else Gua()

    # 优先生成 SVG（可直接返回或用于 PNG 转换）
    # 优先使用请求体中提供的布局参数（若有），否则使用后端默认值
    svg_params = {}
    if input.line_thickness is not None:
        svg_params["line_thickness"] = input.line_thickness
    if input.length is not None:
        svg_params["length"] = input.length
    if input.split_gap is not None:
        svg_params["split_gap"] = input.split_gap
    if input.gap_between is not None:
        svg_params["gap_between"] = input.gap_between
    if input.margin is not None:
        svg_params["margin"] = input.margin
    if input.corner_radius is not None:
        svg_params["corner_radius"] = input.corner_radius
    if input.width is not None:
        svg_params["width"] = input.width
    if input.height is not None:
        svg_params["height"] = input.height

    try:
        svg = GuaVisualizer.to_svg(gua, **svg_params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成 SVG 失败: {e}")

    fmt = (format or "").lower()
    if fmt not in ("png", "svg"):
        raise HTTPException(status_code=400, detail="不支持的 format 参数，支持 'png' 或 'svg'。")

    # 如果请求 SVG，直接返回
    if fmt == "svg":
        return Response(content=svg, media_type="image/svg+xml")
    # 直接使用可视化器提供的统一 PNG 生成逻辑，以保证 SVG 与 PNG 表现一致
    try:
        png_bytes = GuaVisualizer.to_png_bytes(gua, **svg_params)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        # 若 Pillow 缺失或生成失败，返回 500
        raise HTTPException(status_code=500, detail=f"生成 PNG 失败: {e}")


@app.post("/api/generate", response_model=GuaResponse)
async def generate_gua(input: GenerateGuaInput):
    """生成卦（若传入 `yaos` 则以该爻为准；否则随机生成）。

    返回结构包含 `name`、`binary`、`value` 与 `yaos` 列表（每项含枚举名与数值）。
    """
    try:
        yaos = _parse_yaos(input.yaos) if input.yaos else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gua = Gua(yaos=yaos) if yaos is not None else Gua()

    yaos_out = []
    for y in gua.yaos:
        # Enum: name and value
        yaos_out.append({"name": y.name, "value": y.value})

    return GuaResponse(name=gua.name, binary=gua.binary, value=gua.value, yaos=yaos_out)


@app.get("/api/history", response_model=List[HistoryRead])
async def list_history(limit: int = 100):
    session = _db.get_session()
    try:
        stmt = select(_db.History).order_by(_db.History.created_at.desc()).limit(limit)
        results = session.exec(stmt).all()
        out = []
        import json as _json

        for h in results:
            yaos = None
            try:
                if h.yaos_json:
                    yaos = _json.loads(h.yaos_json)
            except Exception:
                yaos = None
            out.append(
                HistoryRead(
                    id=h.id,
                    question=h.question,
                    yaos=yaos,
                    response_text=h.response_text,
                    mode=h.mode,
                    created_at=h.created_at.isoformat(),
                )
            )
        return out
    finally:
        session.close()


@app.get("/api/history/{history_id}", response_model=HistoryRead)
async def get_history(history_id: int):
    session = _db.get_session()
    try:
        h = session.get(_db.History, history_id)
        if not h:
            raise HTTPException(status_code=404, detail="历史记录未找到")
        import json as _json

        yaos = None
        try:
            if h.yaos_json:
                yaos = _json.loads(h.yaos_json)
        except Exception:
            yaos = None
        return HistoryRead(
            id=h.id,
            question=h.question,
            yaos=yaos,
            response_text=h.response_text,
            mode=h.mode,
            created_at=h.created_at.isoformat(),
        )
    finally:
        session.close()


@app.delete("/api/history/{history_id}")
async def delete_history_item(history_id: int):
    session = _db.get_session()
    try:
        h = session.get(_db.History, history_id)
        if not h:
            raise HTTPException(status_code=404, detail="历史记录未找到")
        session.delete(h)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@app.patch("/api/history/{history_id}", response_model=HistoryRead)
async def update_history(history_id: int, update: HistoryUpdate):
    session = _db.get_session()
    try:
        h = session.get(_db.History, history_id)
        if not h:
            raise HTTPException(status_code=404, detail="历史记录未找到")
        import json as _json

        if update.question is not None:
            h.question = update.question
        if update.yaos is not None:
            try:
                h.yaos_json = _json.dumps(update.yaos, ensure_ascii=False)
            except Exception:
                h.yaos_json = None

        session.add(h)
        session.commit()
        session.refresh(h)

        yaos = None
        try:
            if h.yaos_json:
                yaos = _json.loads(h.yaos_json)
        except Exception:
            yaos = None

        return HistoryRead(
            id=h.id,
            question=h.question,
            yaos=yaos,
            response_text=h.response_text,
            mode=h.mode,
            created_at=h.created_at.isoformat(),
        )
    finally:
        session.close()


@app.delete("/api/history")
async def clear_history():
    session = _db.get_session()
    try:
        session.exec(select(_db.History)).all()
        # 简单清空表
        session.exec("DELETE FROM history")
        session.commit()
        return {"ok": True}
    finally:
        session.close()

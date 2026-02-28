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


app = FastAPI(title="Gua4Destiny API", version="0.1.0")

resolver = GuaResolver()


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
    try:
        # 使用与可视化器一致的默认尺寸（宽:800，高:360），以保证 SVG->PNG 比例一致
        svg = GuaVisualizer.to_svg(
            gua, width=800, height=360, line_thickness=16, line_spacing=44, margin=24, split_gap=28
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成 SVG 失败: {e}")

    fmt = (format or "").lower()
    if fmt not in ("png", "svg"):
        raise HTTPException(status_code=400, detail="不支持的 format 参数，支持 'png' 或 'svg'。")

    # 如果请求 SVG，直接返回
    if fmt == "svg":
        return Response(content=svg, media_type="image/svg+xml")

    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
        return Response(content=png_bytes, media_type="image/png")
    except Exception:
        # 回退到 Pillow 简单渲染（仍然可用）
        if Image is None:
            raise HTTPException(status_code=500, detail="无法生成图片：缺少 cairosvg 与 Pillow")

        # Pillow 回退：按 GuaVisualizer 相同布局绘制，保证尺寸一致
        width, height = 800, 360
        margin = 24
        line_thickness = 16
        line_spacing = 44

        img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        text = f"{gua.name} ({gua.binary})"
        text_y = margin // 2 + 8
        draw.text((width // 2 - 10 * len(text) // 2, text_y), text, fill=(0, 0, 0), font=font)

        # 绘制六爻（与 SVG 相同，从下到上）
        y_positions = [height - margin - i * line_spacing for i in range(6)]
        for index, bit in enumerate(gua.binary):
            # visualizer uses index order 0..5 mapping to y_positions[0]..; keep same
            y = y_positions[index] - line_thickness // 2
            if bit == "1":
                draw.rectangle((margin, y, width - margin, y + line_thickness), fill=(0, 0, 0))
            else:
                half_width = (width - 2 * margin - 28) // 2
                draw.rectangle((margin, y, margin + half_width, y + line_thickness), fill=(0, 0, 0))
                draw.rectangle((margin + half_width + 28, y, margin + half_width + 28 + half_width, y + line_thickness), fill=(0, 0, 0))

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.read(), media_type="image/png")


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

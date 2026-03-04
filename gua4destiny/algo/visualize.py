from __future__ import annotations

from pathlib import Path
from typing import Sequence
from urllib.parse import quote

from .gua_model import Gua
from .gua_types import YinYangType


class GuaVisualizer:
    """根据 Gua 生成 SVG 图片，支持 UI 嵌入与文件保存。"""

    @classmethod
    def to_svg(
        cls,
        gua: Gua,
        *,
        # 新的默认布局参数（根据你的设计）
        line_thickness: int = 100,  # 横线高度
        length: int = 900,  # 横线总体长度（不含左右外边距）
        split_gap: int = 300,  # 中断（阴爻两段间隙）
        line_spacing: int | None = None,  # 若为 None，则按 gap_between + line_thickness 计算
        gap_between: int = 100,  # 爻之间的空隙（线条之间的可见间距）
        margin: int = 200,  # 外围左右与上下边距
        width: int | None = None,  # 会根据 length 和 margin 计算默认 width
        foreground: str = "#111111",
        background: str = "#FFFFFF",
        corner_radius: int | None = 50,
        height: int | None = None,
    ) -> str:
        # 计算画布宽度与高度
        if width is None:
            width = margin * 2 + length

        # 若未给出 line_spacing，按 line_thickness + gap_between 计算
        if line_spacing is None:
            line_spacing = line_thickness + gap_between

        # 高度：2*margin + (6-1)*line_spacing + line_thickness，若外部传入 height 则覆盖
        computed_height = 2 * margin + (6 - 1) * line_spacing + line_thickness
        height = int(height) if height is not None else computed_height

        cls._validate_layout(width, height, line_thickness, line_spacing, margin, split_gap)

        lines = cls._normalize_yaos(gua)

        # 纵向间距计算：line_spacing 表示中心到中心的步长；若用户传入 None，则按 (line_thickness + gap_between)
        if line_spacing is None:
            line_spacing = line_thickness + gap_between

        # 纵向位置：从上到下
        y_positions = [margin + i * line_spacing for i in range(6)]
        rects: list[str] = []

        # 计算半段宽度
        usable_width = width - 2 * margin
        half_width = (usable_width - split_gap) // 2

        # 保证 corner_radius 合理
        if corner_radius is None:
            corner_radius = max(2, line_thickness // 2)

        for index, line_type in enumerate(lines):
            y = y_positions[index] - line_thickness // 2
            if line_type == YinYangType.Yang:
                rects.append(
                    cls._rect(x=margin, y=y, width=usable_width, height=line_thickness, fill=foreground, rx=corner_radius)
                )
            else:
                rects.append(
                    cls._rect(x=margin, y=y, width=half_width, height=line_thickness, fill=foreground, rx=corner_radius)
                )
                rects.append(
                    cls._rect(x=margin + half_width + split_gap, y=y, width=half_width, height=line_thickness, fill=foreground, rx=corner_radius)
                )

        rect_markup = "\n    ".join(rects)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
            f'  <rect x="0" y="0" width="{width}" height="{height}" fill="{background}"/>\n'
            f'  {rect_markup}\n'
            "</svg>"
        )
        return svg

    @classmethod
    def to_data_uri(cls, gua: Gua, **kwargs) -> str:
        svg = cls.to_svg(gua, **kwargs)
        return "data:image/svg+xml;utf8," + quote(svg)

    @classmethod
    def to_png_bytes(
        cls,
        gua: Gua,
        *,
        # 与 SVG 保持同一套参数名称（优先使用 length/margin 计算宽度）
        line_thickness: int = 100,
        length: int = 900,
        split_gap: int = 300,
        line_spacing: int | None = None,
        gap_between: int = 100,
        margin: int = 200,
        width: int | None = None,
        height: int | None = None,
        foreground: str = "#111111",
        background: str = "#FFFFFF",
        corner_radius: int | None = 50,
    ) -> bytes:
        """使用 Pillow 绘制 PNG，保证与 `to_svg` 布局一致并使用圆角矩形。返回 PNG 字节。"""
        try:
            from PIL import Image, ImageDraw
        except Exception as e:
            raise RuntimeError("Pillow 未安装，无法生成 PNG") from e

        # 计算 width/height
        if width is None:
            width = margin * 2 + length

        # 计算 line_spacing 如果为 None
        if line_spacing is None:
            line_spacing = line_thickness + gap_between

        # 计算高度（若未指定 height）
        if height is None:
            height = 2 * margin + (6 - 1) * line_spacing + line_thickness

        cls._validate_layout(int(width), int(height), line_thickness, line_spacing, margin, split_gap)
        lines = cls._normalize_yaos(gua)

        # 纵向位置：从上到下
        y_positions = [margin + i * line_spacing for i in range(6)]

        img = Image.new("RGBA", (int(width), int(height)), background)
        draw = ImageDraw.Draw(img)

        # 计算圆角半径
        if corner_radius is None:
            corner_radius = max(4, line_thickness // 2)

        fg = foreground

        usable_width = width - 2 * margin
        half_width = (usable_width - split_gap) // 2

        for index, line_type in enumerate(lines):
            y = int(y_positions[index] - line_thickness // 2)
            top = y
            bottom = y + line_thickness
            if line_type == YinYangType.Yang:
                # 整条实线，使用圆角矩形
                draw.rounded_rectangle((margin, top, margin + usable_width, bottom), radius=corner_radius, fill=fg)
            else:
                # 阴爻：左右两段
                left_box = (margin, top, margin + half_width, bottom)
                right_box = (margin + half_width + split_gap, top, margin + half_width + split_gap + half_width, bottom)
                draw.rounded_rectangle(left_box, radius=corner_radius, fill=fg)
                draw.rounded_rectangle(right_box, radius=corner_radius, fill=fg)

        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    @classmethod
    def save_svg(cls, gua: Gua, file_path: str | Path, **kwargs) -> Path:
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        svg = cls.to_svg(gua, **kwargs)
        target.write_text(svg, encoding="utf-8")
        return target

    @staticmethod
    def _normalize_yaos(gua: Gua) -> Sequence[YinYangType]:
        if len(gua.yy) != 6:
            raise ValueError("Gua 必须包含 6 条爻")
        return gua.yy

    @staticmethod
    def _validate_layout(
        width: int,
        height: int,
        line_thickness: int,
        line_spacing: int,
        margin: int,
        split_gap: int,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width 和 height 必须大于 0")
        if line_thickness <= 0 or line_spacing <= 0:
            raise ValueError("line_thickness 和 line_spacing 必须大于 0")
        if margin < 0 or split_gap < 0:
            raise ValueError("margin 和 split_gap 不能为负数")

    @staticmethod
    def _rect(*, x: int, y: int, width: int, height: int, fill: str, rx: int | None = None) -> str:
        # 在 SVG 中使用 rx 表示圆角半径；若未提供，默认为 2
        rx_val = int(rx) if rx is not None else 2
        return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill}" rx="{rx_val}"/>'

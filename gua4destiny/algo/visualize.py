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
        width: int = 240,
        height: int = 360,
        line_thickness: int = 16,
        line_spacing: int = 44,
        margin: int = 24,
        split_gap: int = 28,
        foreground: str = "#111111",
        background: str = "#FFFFFF",
        title: str | None = None,
    ) -> str:
        cls._validate_layout(width, height, line_thickness, line_spacing, margin, split_gap)

        lines = cls._normalize_yaos(gua)
        label = title if title is not None else gua.name

        y_positions = [height - margin - i * line_spacing for i in range(6)]
        rects: list[str] = []
        for index, line_type in enumerate(lines):
            y = y_positions[index] - line_thickness // 2
            if line_type == YinYangType.Yang:
                rects.append(
                    cls._rect(
                        x=margin,
                        y=y,
                        width=width - 2 * margin,
                        height=line_thickness,
                        fill=foreground,
                    )
                )
            else:
                half_width = (width - 2 * margin - split_gap) // 2
                rects.append(
                    cls._rect(
                        x=margin,
                        y=y,
                        width=half_width,
                        height=line_thickness,
                        fill=foreground,
                    )
                )
                rects.append(
                    cls._rect(
                        x=margin + half_width + split_gap,
                        y=y,
                        width=half_width,
                        height=line_thickness,
                        fill=foreground,
                    )
                )

        text_y = margin // 2 + 8
        text = (
            f'<text x="{width / 2}" y="{text_y}" text-anchor="middle" '
            f'font-size="16" fill="{foreground}">{label}</text>'
            if label
            else ""
        )

        rect_markup = "\n    ".join(rects)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">\n'
            f'  <rect x="0" y="0" width="{width}" height="{height}" fill="{background}"/>\n'
            f'  {text}\n'
            f'  {rect_markup}\n'
            "</svg>"
        )
        return svg

    @classmethod
    def to_data_uri(cls, gua: Gua, **kwargs) -> str:
        svg = cls.to_svg(gua, **kwargs)
        return "data:image/svg+xml;utf8," + quote(svg)

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
    def _rect(*, x: int, y: int, width: int, height: int, fill: str) -> str:
        return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill}" rx="2"/>'

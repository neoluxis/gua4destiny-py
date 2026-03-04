from __future__ import annotations

from pathlib import Path

try:
    from gua4destiny.algo import Gua, GuaVisualizer, YarrowStalkEngine
except ModuleNotFoundError:
    import sys

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from gua4destiny.algo import Gua, GuaVisualizer, YarrowStalkEngine


def run_demo() -> None:
    engine = YarrowStalkEngine()
    # 使用引擎生成一组爻，也可以替换为固定序列以便可复现
    yaos = engine.six_yaos()
    gua = Gua(yaos)

    out_dir = Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    svg_path = out_dir / f"gua.svg"
    png_path = out_dir / f"gua.png"

    # 保存 SVG 与 PNG，使用统一的大尺寸布局
    svg_params = dict(line_thickness=100, length=1200, split_gap=200, gap_between=100, margin=200, corner_radius=50)
    saved_svg = GuaVisualizer.save_svg(gua, svg_path, **svg_params)

    # 生成 PNG bytes 并保存（与 SVG 参数一致）
    try:
        png_bytes = GuaVisualizer.to_png_bytes(gua, **svg_params)
        with open(png_path, "wb") as f:
            f.write(png_bytes)
        saved_png = png_path
    except Exception as e:
        saved_png = None
        print("生成 PNG 失败:", e)

    data_uri = GuaVisualizer.to_data_uri(gua)

    print("卦象:", gua)
    print("SVG 已保存:", saved_svg)
    print("PNG 已保存:", saved_png)
    print("data URI 前缀:", data_uri[:80] + "...")


if __name__ == "__main__":
    run_demo()

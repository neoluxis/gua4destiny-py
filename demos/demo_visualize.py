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
    gua = Gua(engine.six_yaos())

    out_file = Path(__file__).parent / "outputs" / f"gua_{gua.name}.svg"
    saved = GuaVisualizer.save_svg(gua, out_file)
    data_uri = GuaVisualizer.to_data_uri(gua)

    print("卦象:", gua)
    print("SVG 已保存:", saved)
    print("data URI 前缀:", data_uri[:80] + "...")


if __name__ == "__main__":
    run_demo()

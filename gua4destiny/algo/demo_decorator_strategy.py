from __future__ import annotations

import random

try:
    from gua4destiny.algo import (
        Divider,
        DivisionStrategy,
        Gua,
        YarrowStalkEngine,
        division_method,
    )
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    from gua4destiny.algo import (
        Divider,
        DivisionStrategy,
        Gua,
        YarrowStalkEngine,
        division_method,
    )


@division_method("M")
class MedianLikeDivisionStrategy(DivisionStrategy):
    """示例策略：中间概率高、两边概率低（有界在 [0, omni]）"""

    def divide(self, omni: int, parts: int, **kwargs):
        self.validate(omni, parts)
        if omni == 0:
            return [0 for _ in range(parts)]
        if parts == 1:
            return [omni]

        alpha = float(kwargs.pop("alpha", 3.0))
        beta = float(kwargs.pop("beta", 3.0))
        if kwargs:
            unknown = ", ".join(sorted(kwargs.keys()))
            raise ValueError(f"分割方法 M 不支持参数: {unknown}")

        cuts = []
        for _ in range(parts - 1):
            x = random.betavariate(alpha, beta)
            point = int(round(x * omni))
            if omni > 1:
                point = min(max(1, point), omni - 1)
            else:
                point = omni
            cuts.append(point)

        points = [0] + sorted(cuts) + [omni]
        return [points[i + 1] - points[i] for i in range(parts)]


def run_demo() -> None:
    divider = Divider()
    split_params = {"alpha": 4.5, "beta": 4.5}

    print("M 方法分割 49 ->", divider.divide(49, 2, method="M", **split_params))

    engine = YarrowStalkEngine(divider=divider, divide_method="M", divide_kwargs=split_params)
    yaos = engine.six_yaos()
    gua = Gua(yaos)

    print("六爻:", [y.value for y in yaos])
    print("卦象:", gua)


if __name__ == "__main__":
    run_demo()

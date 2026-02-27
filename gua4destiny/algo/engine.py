from __future__ import annotations

from typing import Any, Dict, List

from .constants import LE_YONG, VALID_YONG_RETURNS
from .division import Divider
from .gua_types import YaoType


class YarrowStalkEngine:
    """大衍筮法引擎（可注入分割策略）"""

    def __init__(
        self,
        divider: Divider | None = None,
        divide_method: str = "N",
        divide_kwargs: Dict[str, Any] | None = None,
    ) -> None:
        self.divider = divider or Divider()
        self.divide_method = divide_method
        self.divide_kwargs = divide_kwargs or {}

    def one_change(self, yong: int, **divide_kwargs) -> tuple[int, int]:
        merged_kwargs = {**self.divide_kwargs, **divide_kwargs}
        ciel, terre = self.divider.divide(yong, 2, method=self.divide_method, **merged_kwargs)
        homme, terre = 1, terre - 1

        seasons_ciel, return_ciel = divmod(ciel, 4)
        seasons_terre, return_terre = divmod(terre, 4)

        if return_ciel == 0:
            return_ciel = 4
            seasons_ciel -= 1
        if return_terre == 0:
            return_terre = 4
            seasons_terre -= 1

        ret = return_ciel + return_terre + homme
        new_yong = (seasons_ciel + seasons_terre) * 4
        return ret, new_yong

    def three_changes_to_yao(self, **divide_kwargs) -> YaoType:
        yong = LE_YONG
        for step in range(3):
            _, yong = self.one_change(yong, **divide_kwargs)
            assert yong in VALID_YONG_RETURNS[step], f"第{step + 1}变的用数不合法: {yong}"
        return YaoType(yong // 4)

    def six_yaos(self, **divide_kwargs) -> List[YaoType]:
        return [self.three_changes_to_yao(**divide_kwargs) for _ in range(6)]

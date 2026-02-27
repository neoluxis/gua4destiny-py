from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Type, overload

import numpy as np


class DivisionStrategy(ABC):
    @abstractmethod
    def divide(self, omni: int, parts: int, **kwargs: Any) -> List[int]:
        raise NotImplementedError

    @staticmethod
    def validate(omni: int, parts: int) -> None:
        if parts <= 0:
            raise ValueError("分割的份数必须大于0")
        if omni < 0:
            raise ValueError("待分割的总量必须非负")


_DIVISION_STRATEGY_REGISTRY: Dict[str, Type[DivisionStrategy]] = {}


def division_method(key: str):
    """使用装饰器注册分割策略类。

    示例:
        @division_method("N")
        class NormalDivisionStrategy(DivisionStrategy):
            ...
    """

    normalized_key = key.strip().upper()

    def decorator(strategy_cls: Type[DivisionStrategy]) -> Type[DivisionStrategy]:
        if not issubclass(strategy_cls, DivisionStrategy):
            raise TypeError("被注册对象必须继承 DivisionStrategy")
        _DIVISION_STRATEGY_REGISTRY[normalized_key] = strategy_cls
        return strategy_cls

    return decorator


@division_method("U")
class UniformDivisionStrategy(DivisionStrategy):
    def divide(self, omni: int, parts: int, **kwargs: Any) -> List[int]:
        self.validate(omni, parts)
        if kwargs:
            _raise_unknown_kwargs("U", kwargs)
        if parts == 1:
            return [omni]
        if omni <= 1:
            head = [0 for _ in range(parts)]
            head[-1] = omni
            return head
        points = sorted(random.sample(range(1, omni), parts - 1))
        points = [0] + points + [omni]
        return [points[i + 1] - points[i] for i in range(parts)]


@division_method("N")
class NormalDivisionStrategy(DivisionStrategy):
    def divide(self, omni: int, parts: int, **kwargs: Any) -> List[int]:
        self.validate(omni, parts)
        std_ratio = kwargs.pop("std_ratio", 0.5)
        mean = kwargs.pop("mean", omni / parts)
        std_dev = kwargs.pop("std_dev", mean * std_ratio)
        if kwargs:
            _raise_unknown_kwargs("N", kwargs)
        values = np.random.normal(mean, std_dev, parts)
        return _normalize_to_total(values, omni)


@division_method("E")
class ExponentialDivisionStrategy(DivisionStrategy):
    def divide(self, omni: int, parts: int, **kwargs: Any) -> List[int]:
        self.validate(omni, parts)
        scale = kwargs.pop("scale", omni / parts)
        if kwargs:
            _raise_unknown_kwargs("E", kwargs)
        values = np.random.exponential(scale, parts)
        return _normalize_to_total(values, omni)


@division_method("P")
class PoissonDivisionStrategy(DivisionStrategy):
    def divide(self, omni: int, parts: int, **kwargs: Any) -> List[int]:
        self.validate(omni, parts)
        lam = kwargs.pop("lam", omni / parts)
        if kwargs:
            _raise_unknown_kwargs("P", kwargs)
        values = np.random.poisson(lam, parts)
        return _normalize_to_total(values, omni)


class Divider:
    """分割上下文，基于策略名路由"""

    def __init__(self) -> None:
        self._strategies: Dict[str, DivisionStrategy] = {
            key: strategy_cls() for key, strategy_cls in _DIVISION_STRATEGY_REGISTRY.items()
        }

    def register(self, key: str, strategy: DivisionStrategy) -> None:
        self._strategies[key] = strategy

    @overload
    def divide(self, omni: int, parts: int, method: Literal["U"] = "U") -> List[int]:
        ...

    @overload
    def divide(
        self,
        omni: int,
        parts: int,
        method: Literal["N"],
        *,
        std_ratio: float = 0.5,
        mean: float | None = None,
        std_dev: float | None = None,
    ) -> List[int]:
        ...

    @overload
    def divide(self, omni: int, parts: int, method: Literal["E"], *, scale: float | None = None) -> List[int]:
        ...

    @overload
    def divide(self, omni: int, parts: int, method: Literal["P"], *, lam: float | None = None) -> List[int]:
        ...

    @overload
    def divide(self, omni: int, parts: int, method: str, **kwargs: Any) -> List[int]:
        ...

    def divide(self, omni: int, parts: int, method: str = "U", **kwargs: Any) -> List[int]:
        normalized_method = method.strip().upper()
        strategy = self._strategies.get(normalized_method)
        if strategy is None:
            raise ValueError(f"未知的分割方法: {method}")
        return strategy.divide(omni, parts, **kwargs)


def _normalize_to_total(values: np.ndarray, omni: int) -> List[int]:
    total = float(values.sum())
    if total <= 0:
        base = [0 for _ in range(len(values))]
        if base:
            base[-1] = omni
        return base

    divisions = [max(0, int(value / total * omni)) for value in values]
    difference = omni - sum(divisions)
    if divisions:
        divisions[-1] += difference
    return divisions


def _raise_unknown_kwargs(method: str, kwargs: Dict[str, Any]) -> None:
    unknown = ", ".join(sorted(kwargs.keys()))
    raise ValueError(f"分割方法 {method} 不支持参数: {unknown}")

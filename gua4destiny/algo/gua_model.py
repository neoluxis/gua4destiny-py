from __future__ import annotations

from typing import List

from .category import GuaCategoryRepository
from .gua_types import YinYang, YinYangType, YaoType


class Gua:
    """卦对象（值对象风格）"""

    def __init__(self, yaos: List[YaoType]):
        if len(yaos) != 6:
            raise ValueError("卦必须有六爻")
        self.yaos = yaos
        self.yy = [YinYang.get_yin_yang(yao) for yao in yaos]
        self.gua_category = GuaCategoryRepository.get()
        self.binary = self.get_binary_representation()
        self.value = self.get_binary_value()
        self.name = self.get_name()

    def get_index(self) -> int:
        index = self.gua_category["index"].get(str(self.value))
        if index is None:
            raise ValueError(f"未找到二进制数 {self.value} 对应的索引")
        return index

    def get_name(self) -> str:
        index = self.get_index()
        name = self.gua_category["names"].get(str(index))
        if name is None:
            raise ValueError(f"未找到索引 {index} 对应的卦名")
        return name

    def get_binary_representation(self) -> str:
        return "".join("1" if yy == YinYangType.Yang else "0" for yy in self.yy)

    def get_binary_value(self) -> int:
        return int(self.binary, 2)

    def __str__(self) -> str:
        return f"Gua(name='{self.name}', binary='{self.binary}', value={self.value})"

    def __repr__(self) -> str:
        return self.__str__()

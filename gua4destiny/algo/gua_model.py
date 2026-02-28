from __future__ import annotations

from typing import List, Optional

from .category import GuaCategoryRepository
from .gua_types import YinYang, YinYangType, YaoType
from .text_api import FullTextResult, TextAPI


_default_text_api: Optional[TextAPI] = None


class Gua:
    """卦对象（值对象风格）"""

    def __init__(self, yaos: List[YaoType] = None):
        if yaos is None:
            from .engine import YarrowStalkEngine
            from . import Divider, DivisionStrategy
            
            engine = YarrowStalkEngine(divider=Divider(), divide_method="N")
            yaos = engine.six_yaos()

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

    def get_full_text(
        self, *, text_api: Optional[TextAPI] = None, use_cache: bool = True
    ) -> str:
        """获取当前卦象对应的《周易》全文。"""
        api = text_api or _get_default_text_api()
        pinyin_ascii = self.gua_category.get("pinyin_ascii", {}).get(
            str(self.get_index())
        )
        return api.fetch_gua_fulltext(
            name=self.name,
            index=self.get_index(),
            pinyin_ascii=pinyin_ascii,
            use_cache=use_cache,
        )

    def get_full_text_result(
        self, *, text_api: Optional[TextAPI] = None, use_cache: bool = True
    ) -> FullTextResult:
        """获取全文及来源元数据（URL、缓存命中等）。"""
        api = text_api or _get_default_text_api()
        pinyin_ascii = self.gua_category.get("pinyin_ascii", {}).get(
            str(self.get_index())
        )
        return api.fetch_gua_fulltext_result(
            name=self.name,
            index=self.get_index(),
            pinyin_ascii=pinyin_ascii,
            use_cache=use_cache,
        )

    def __str__(self) -> str:
        return f"Gua(name='{self.name}', binary='{self.binary}', value={self.value})"

    def __repr__(self) -> str:
        return self.__str__()


def _get_default_text_api() -> TextAPI:
    global _default_text_api
    if _default_text_api is None:
        _default_text_api = TextAPI()
    return _default_text_api

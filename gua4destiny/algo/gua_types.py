from __future__ import annotations

from enum import Enum


class YaoType(Enum):
    """归奇类型"""

    Vieux_Lune = 6  # 老阴
    Jeune_Soleil = 7  # 少阳
    Jeune_Lune = 8  # 少阴
    Vieux_Soleil = 9  # 老阳


class YinYangType(Enum):
    Yin = 0
    Yang = 1


class YinYang:
    """阴阳类型工具"""

    @classmethod
    def get_yin_yang(cls, yao_type: YaoType) -> YinYangType:
        if yao_type in (YaoType.Vieux_Lune, YaoType.Jeune_Lune):
            return YinYangType.Yin
        if yao_type in (YaoType.Jeune_Soleil, YaoType.Vieux_Soleil):
            return YinYangType.Yang
        raise ValueError("未知的爻类型")

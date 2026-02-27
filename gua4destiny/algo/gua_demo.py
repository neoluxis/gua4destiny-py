LE_GRAND_YAN = 50  # 大衍之数五十
LE_YONG = 49  # 其用四十有九

import random
import math
import numpy as np
import scipy.stats as stats
from typing import List
from enum import Enum
from pathlib import Path
import os
import json
import time

class Division:
    @classmethod
    def divide_by_U(cls, omni: int, p: int) -> List[int]:
        """使用均匀分布进行分割
        @param omni: 待分割的总量
        @param p: 分割的份数
        """
        if p <= 0:
            raise ValueError("分割的份数必须大于0")
        if omni < 0:
            raise ValueError("待分割的总量必须非负")

        # 生成p-1个随机数，作为分割点
        points = sorted(random.sample(range(1, omni), p - 1))
        points = [0] + points + [omni]  # 添加起点和终点

        # 计算每份的大小
        divisions = [points[i + 1] - points[i] for i in range(p)]
        return divisions

    @classmethod
    def divide_by_N(cls, omni: int, p: int) -> List[int]:
        """使用正态分布进行分割
        @param omni: 待分割的总量
        @param p: 分割的份数
        """
        if p <= 0:
            raise ValueError("分割的份数必须大于0")
        if omni < 0:
            raise ValueError("待分割的总量必须非负")

        # 生成p个正态分布的随机数
        mean = omni / p
        std_dev = mean / 2  # 标准差可以根据需要调整
        random_values = np.random.normal(mean, std_dev, p)

        # 将随机数归一化，使其总和为omni
        total = sum(random_values)
        divisions = [max(0, int(value / total * omni)) for value in random_values]

        # 调整最后一份以确保总和为omni
        difference = omni - sum(divisions)
        divisions[-1] += difference

        return divisions

    @classmethod
    def divide_by_E(cls, omni: int, p: int) -> List[int]:
        """使用指数分布进行分割
        @param omni: 待分割的总量
        @param p: 分割的份数
        """
        if p <= 0:
            raise ValueError("分割的份数必须大于0")
        if omni < 0:
            raise ValueError("待分割的总量必须非负")

        # 生成p个指数分布的随机数
        scale = omni / p  # 平均值可以根据需要调整
        random_values = np.random.exponential(scale, p)

        # 将随机数归一化，使其总和为omni
        total = sum(random_values)
        divisions = [max(0, int(value / total * omni)) for value in random_values]

        # 调整最后一份以确保总和为omni
        difference = omni - sum(divisions)
        divisions[-1] += difference

        return divisions

    @classmethod
    def divide_by_P(cls, omni: int, p: int) -> List[int]:
        """使用泊松分布进行分割
        @param omni: 待分割的总量
        @param p: 分割的份数
        """
        if p <= 0:
            raise ValueError("分割的份数必须大于0")
        if omni < 0:
            raise ValueError("待分割的总量必须非负")

        # 生成p个泊松分布的随机数
        lam = omni / p  # 平均值可以根据需要调整
        random_values = np.random.poisson(lam, p)

        # 将随机数归一化，使其总和为omni
        total = sum(random_values)
        divisions = [max(0, int(value / total * omni)) for value in random_values]

        # 调整最后一份以确保总和为omni
        difference = omni - sum(divisions)
        divisions[-1] += difference

        return divisions

    @classmethod
    def divide(cls, omni: int, p: int, method: str = "U") -> List[int]:
        """根据指定的方法进行分割
        @param omni: 待分割的总量
        @param p: 分割的份数
        @param method: 分割方法，'U'表示均匀分布，'N'表示正态分布，'E'表示指数分布，'P'表示泊松分布
        """
        if method == "U":
            return cls.divide_by_U(omni, p)
        elif method == "N":
            return cls.divide_by_N(omni, p)
        elif method == "E":
            return cls.divide_by_E(omni, p)
        elif method == "P":
            return cls.divide_by_P(omni, p)
        else:
            raise ValueError("未知的分割方法")


class YaoType(Enum):
    """归奇类型"""

    Vieux_Lune = 6  # 老阴
    Jeune_Soleil = 7  # 少阳
    Jeune_Lune = 8  # 少阴
    Vieux_Soleil = 9  # 老阳


class YinYang:
    """阴阳类型"""

    class YinYangType(Enum):
        Yin = 0
        Yang = 1

    @classmethod
    def get_yin_yang(cls, yao_type: YaoType) -> YinYang.YinYangType:
        if yao_type in (YaoType.Vieux_Lune, YaoType.Jeune_Lune):
            return cls.YinYangType.Yin
        elif yao_type in (YaoType.Jeune_Soleil, YaoType.Vieux_Soleil):
            return cls.YinYangType.Yang
        else:
            raise ValueError("未知的爻类型")

class GuaCategory:
    """卦类别，从环境变量设置类别，默认为周易后天六十四卦
       提供加载功能
       整个程序运行期间各个类别单例模式
       ```json
       {
        "ZhouyiHoutian": {
        "desc": "周易后天六十四卦",
        "note": "二进制数不为顺序，需转换为索引",
        "index": { // index: value
            "0": 63,
            "1": 0,
            "2": 17,
            ...
        },
        "names": { // index: name
            "0": "乾",
            ...
        }
       }
       ```
    """
    
    _instances = {}
    
    @classmethod
    def get_instance(cls, gua_type: str):
        if gua_type not in cls._instances:
            with open(Path(__file__).parent / "gua_binary2index.json", "r") as f:
                gua_binary2index = json.load(f)
            if gua_type not in gua_binary2index:
                raise ValueError(f"未知的卦类型: {gua_type}")
            cls._instances[gua_type] = gua_binary2index[gua_type]
        return cls._instances[gua_type]
        

class Gua:
    """卦类"""

    def __init__(self, yaos: List[YaoType] = None):
        if yaos is None:
            yaos = SixYao()
        if len(yaos) != 6:
            raise ValueError("卦必须有六爻")
        self.yaos = yaos
        self.yy = [YinYang.get_yin_yang(yao) for yao in yaos]
        self.gua_category = GuaCategory.get_instance(os.getenv("GUA_CATEGORY", "ZhouyiHoutian"))
        self.name = self.get_name()
        self.binary = self.get_binary_representation()
        self.value = self.get_binary_value()
            
    def get_index(self) -> int:
        """将卦的二进制表示转换为对应的索引"""
        binary = self.get_binary_value()
        index = self.gua_category["index"].get(str(binary))
        if index is None:
            raise ValueError(f"未找到二进制数 {binary} 对应的索引")
        return index
        
    def get_name(self) -> str:
        """获取卦的名称"""
        index = self.get_index()
        name = self.gua_category["names"].get(str(index))
        if name is None:
            raise ValueError(f"未找到索引 {index} 对应的卦名")
        return name
        

    def get_binary_representation(self) -> str:
        """获取卦的二进制表示，阳爻为1，阴爻为0"""
        return "".join("1" if yy == YinYang.YinYangType.Yang else "0" for yy in self.yy)

    def get_binary_value(self) -> int:
        """获取卦的二进制数值表示"""
        binary_representation = self.get_binary_representation()
        return int(binary_representation, 2)

    def __str__(self):
        return f"Gua(name='{self.name}', binary='{self.binary}', value={self.value})"

    def __repr__(self):
        return self.__str__()


valid_ret = [
    [44, 40],
    [40, 36, 32],
    [36, 32, 28, 24],
]


def change(yong: int) -> List[int]:
    """一变"""
    # 分二
    ciel, terre = Division.divide(yong, 2, method="N")
    # 挂一
    homme, terre = 1, terre - 1
    # 碟四
    seasons_ciel, return_ciel = ciel // 4, ciel % 4
    seasons_terre, return_terre = terre // 4, terre % 4
    if return_ciel == 0:
        return_ciel = 4
        seasons_ciel -= 1
    if return_terre == 0:
        return_terre = 4
        seasons_terre -= 1
    # 归奇
    ret = return_ciel + return_terre + homme
    return ret, (seasons_ciel + seasons_terre) * 4


def change3() -> int:
    """三变出一爻"""
    yong = LE_YONG
    ret_val = 0
    for t in range(3):
        ret, yong = change(yong)
        ret_val += ret
        assert yong in valid_ret[t], f"第{t+1}变的用数不合法: {yong}"
    yao = yong // 4
    return YaoType(yao)


def SixYao() -> List[YaoType]:
    """生成一卦六爻"""
    return [change3() for _ in range(6)]


if __name__ == "__main__":
    for _ in range(3):
        print(Gua())
        time.sleep(0.5)

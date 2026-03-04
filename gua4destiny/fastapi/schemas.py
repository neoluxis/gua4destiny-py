from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field


class GuaInput(BaseModel):
    question: str = Field(..., description="用户的问题，例如：考试成绩如何？")
    yaos: Optional[List[Union[str, int]]] = Field(
        None, description="六爻列表，支持枚举名字符串或枚举整数值；若为空则随机生成"
    )


class ResolveResponse(BaseModel):
    text: str


class GenerateGuaInput(BaseModel):
    yaos: Optional[List[Union[str, int]]] = Field(
        None, description="六爻列表（可选），支持枚举名或整数；为空则随机生成"
    )
    # 可选的可视化布局参数（传入以覆盖后端默认布局）
    line_thickness: Optional[int] = Field(None, description="横线高度（像素）")
    length: Optional[int] = Field(None, description="横线总体长度（像素），不含两侧外边距")
    split_gap: Optional[int] = Field(None, description="阴爻中断长度（像素）")
    gap_between: Optional[int] = Field(None, description="爻之间的可见空隙（像素）")
    margin: Optional[int] = Field(None, description="外围边距（像素）")
    corner_radius: Optional[int] = Field(None, description="圆角半径（像素）")
    width: Optional[int] = Field(None, description="画布宽度（像素），优先于 length+margin")
    height: Optional[int] = Field(None, description="画布高度（像素），可覆盖计算高度")


class GuaYao(BaseModel):
    name: str
    value: int


class GuaResponse(BaseModel):
    name: str
    binary: str
    value: int
    yaos: List[GuaYao]


class HistoryCreate(BaseModel):
    question: str
    yaos: Optional[List[Union[str, int]]] = None
    mode: str = "resolve"


class HistoryRead(BaseModel):
    id: int
    question: str
    yaos: Optional[List[Union[str, int]]] = None
    response_text: Optional[str] = None
    mode: str
    created_at: str


class HistoryUpdate(BaseModel):
    question: Optional[str] = Field(None, description="更新后的问题文本")
    yaos: Optional[List[Union[str, int]]] = Field(None, description="可选的六爻列表以更新历史条目")

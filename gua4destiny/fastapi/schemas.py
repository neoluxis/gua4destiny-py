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


class GuaYao(BaseModel):
    name: str
    value: int


class GuaResponse(BaseModel):
    name: str
    binary: str
    value: int
    yaos: List[GuaYao]

from __future__ import annotations

import datetime
import json
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = "sqlite:///./gua_history.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class History(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    yaos_json: Optional[str] = None
    response_text: Optional[str] = None
    mode: str = "resolve"
    # 使用本地时区的时间（带时区信息），便于前端按本地时间显示
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).astimezone()
    )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

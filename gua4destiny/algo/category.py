from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any


class GuaCategoryRepository:
    """卦类别仓库（按类别名缓存，单例风格）"""

    _instances: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get(cls, gua_type: str | None = None) -> Dict[str, Any]:
        resolved_type = gua_type or os.getenv("GUA_CATEGORY", "ZhouyiHoutian")
        if resolved_type not in cls._instances:
            mapping_file = Path(__file__).parent / "gua_binary2index.json"
            with open(mapping_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if resolved_type not in data:
                raise ValueError(f"未知的卦类型: {resolved_type}")
            cls._instances[resolved_type] = data[resolved_type]
        return cls._instances[resolved_type]

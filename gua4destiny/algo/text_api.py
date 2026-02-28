"""Utilities for fetching full text of gua pages.

目标：让全文获取更契合现有模块（Gua/category/pinyin/ui link）。

Features:
- requests.Session + rotating User-Agent
- polite rate limiting with jitter
- retry with exponential backoff
- local cache under .cache/text_api
- multi-source fallback: wikisource(name) -> wikisource(trad) -> ctext(pinyin)
- structured result metadata for downstream modules
"""
from __future__ import annotations

from dataclasses import dataclass
import random
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .category import GuaCategoryRepository


DEFAULT_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36",
]


@dataclass
class FullTextResult:
    text: str
    source_url: str
    cache_hit: bool
    source_key: str


class TextAPI:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        min_delay: float = 0.8,
        max_delay: float = 1.6,
        max_retries: int = 4,
        timeout: float = 15.0,
        user_agents: Optional[list[str]] = None,
    ) -> None:
        self.session = requests.Session()
        self.user_agents = user_agents or DEFAULT_UA_LIST
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.max_retries = int(max_retries)
        self.timeout = float(timeout)
        root = cache_dir or Path.cwd() / ".cache" / "text_api"
        self.cache_dir = Path(root)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._gua_category = GuaCategoryRepository.get()

    def _choose_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _polite_sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.cache_dir / f"{safe}.txt"

    def _resolve_index(self, name: Optional[str], index: Optional[int]) -> Optional[int]:
        if index is not None:
            return index
        if not name:
            return None
        names = self._gua_category.get("names", {})
        for index_key, gua_name in names.items():
            if gua_name == name:
                return int(index_key)
        return None

    def _resolve_pinyin(self, name: Optional[str], index: Optional[int], pinyin_ascii: Optional[str]) -> Optional[str]:
        if pinyin_ascii:
            return pinyin_ascii
        resolved_index = self._resolve_index(name, index)
        if resolved_index is None:
            return None
        pinyin_map = self._gua_category.get("pinyin_ascii", {})
        return pinyin_map.get(str(resolved_index))

    def _candidate_endpoints(
        self,
        *,
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        resolved_pinyin = self._resolve_pinyin(name, index, pinyin_ascii)

        if name:
            candidates.append(("wikisource_name", f"https://zh.wikisource.org/wiki/周易/{name}"))
            trad = _to_traditional_guess(name)
            if trad != name:
                candidates.append(("wikisource_name_trad", f"https://zh.wikisource.org/wiki/周易/{trad}"))

        if resolved_pinyin:
            candidates.append(("ctext_pinyin", f"https://ctext.org/book-of-changes/{resolved_pinyin}/zh"))

        seen = set()
        uniq: list[tuple[str, str]] = []
        for source_key, url in candidates:
            if url in seen:
                continue
            seen.add(url)
            uniq.append((source_key, url))
        return uniq

    def fetch_gua_fulltext_result(
        self,
        name: Optional[str] = None,
        *,
        index: Optional[int] = None,
        pinyin_ascii: Optional[str] = None,
        use_cache: bool = True,
    ) -> FullTextResult:
        resolved_name = name or (self._gua_category.get("names", {}).get(str(index)) if index is not None else None)
        cache_key = str(index) if index is not None else (resolved_name or pinyin_ascii or "unknown")
        cache_file = self._cache_path(cache_key)

        if use_cache and cache_file.exists():
            try:
                return FullTextResult(
                    text=cache_file.read_text(encoding="utf-8"),
                    source_url="cache://local",
                    cache_hit=True,
                    source_key="cache",
                )
            except Exception:
                pass

        candidates = self._candidate_endpoints(name=resolved_name, index=index, pinyin_ascii=pinyin_ascii)
        if not candidates:
            raise ValueError("无法确定全文来源，请至少提供 name/index/pinyin_ascii 之一")

        last_exc: Optional[Exception] = None
        for source_key, url in candidates:
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = self.session.get(url, headers=self._choose_headers(), timeout=self.timeout)
                    resp.raise_for_status()
                    text = self._extract_main_text(resp.text, resolved_name or "")
                    if not text.strip():
                        raise RuntimeError("正文解析为空")

                    try:
                        cache_file.write_text(text, encoding="utf-8")
                    except Exception:
                        pass

                    self._polite_sleep()
                    return FullTextResult(
                        text=text,
                        source_url=url,
                        cache_hit=False,
                        source_key=source_key,
                    )
                except Exception as exc:
                    last_exc = exc
                    time.sleep((2 ** (attempt - 1)) + random.random())

        attempted = ", ".join(url for _, url in candidates)
        raise RuntimeError(f"无法获取全文，已尝试: {attempted}") from last_exc

    def fetch_gua_fulltext(
        self,
        name: Optional[str] = None,
        *,
        index: Optional[int] = None,
        pinyin_ascii: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        result = self.fetch_gua_fulltext_result(
            name=name,
            index=index,
            pinyin_ascii=pinyin_ascii,
            use_cache=use_cache,
        )
        return result.text

    def _extract_main_text(self, html: str, title: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        content = soup.find(id="mw-content-text") or soup.find(class_="mw-parser-output")
        if content:
            for bad in content.select("script, style, .mw-editsection, .navbox, table.toc"):
                bad.decompose()

            cleaned = _clean_text_block(content.get_text(separator="\n"))
            idx = cleaned.find(title) if title else -1
            if idx >= 0:
                cleaned = cleaned[idx:]
            return cleaned.strip()

        cleaned = _clean_text_block(soup.get_text(separator="\n"))
        if title:
            try:
                lines = cleaned.splitlines()
                idx1 = next(i for i, line in enumerate(lines) if title in line)
                idx2 = next(
                    (
                        i
                        for i, line in enumerate(lines[idx1 + 1 :], start=idx1 + 1)
                        if "隐私政策" in line or "隱私政策" in line
                    ),
                    len(lines),
                )
                return "\n".join(lines[idx1:idx2]).strip()
            except StopIteration:
                pass
        return cleaned.strip()


def _clean_text_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    output: list[str] = []
    last_empty = False
    for line in lines:
        if not line.strip():
            if not last_empty:
                output.append("")
            last_empty = True
            continue
        output.append(line)
        last_empty = False
    return "\n".join(output)


def _to_traditional_guess(text: str) -> str:
    mapping = str.maketrans(
        {
            "谦": "謙",
            "随": "隨",
            "蛊": "蠱",
            "临": "臨",
            "观": "觀",
            "贲": "賁",
            "剥": "剝",
            "颐": "頤",
            "过": "過",
            "离": "離",
            "恒": "恆",
            "损": "損",
            "兑": "兌",
            "涣": "渙",
            "节": "節",
            "济": "濟",
            "归": "歸",
        }
    )
    return text.translate(mapping)

"""Class-based text fetchers with priority fallback."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import random
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

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


@dataclass
class NamedTextSource:
    name: str
    priority: int


class BaseTextFetcher(ABC):
    name: str = "base"
    priority: int = 100

    @abstractmethod
    def build_endpoints(
        self,
        *,
        api: "TextAPI",
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> list[tuple[str, str]]:
        raise NotImplementedError

    def fetch(self, *, session: requests.Session, url: str, headers: dict, timeout: float) -> str:
        resp = session.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    @abstractmethod
    def extract(
        self,
        *,
        html: str,
        api: "TextAPI",
        source_key: str,
        url: str,
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> str:
        raise NotImplementedError

    def validate(self, text: str) -> bool:
        return bool(text.strip())


_FETCHER_REGISTRY: dict[str, type[BaseTextFetcher]] = {}


def text_fetcher(name: str, priority: int = 100):
    normalized = name.strip().lower()

    def decorator(cls: type[BaseTextFetcher]) -> type[BaseTextFetcher]:
        if not issubclass(cls, BaseTextFetcher):
            raise TypeError("注册对象必须继承 BaseTextFetcher")
        if normalized in _FETCHER_REGISTRY:
            raise ValueError(f"全文源已存在: {normalized}")
        cls.name = normalized
        cls.priority = int(priority)
        _FETCHER_REGISTRY[normalized] = cls
        return cls

    return decorator


@text_fetcher("wikisource", priority=10)
class WikisourceFetcher(BaseTextFetcher):
    def build_endpoints(
        self,
        *,
        api: "TextAPI",
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> list[tuple[str, str]]:
        if not name:
            return []
        endpoints = [("wikisource", f"https://zh.wikisource.org/wiki/周易/{name}")]
        trad = api.to_traditional_name(name=name, pinyin_ascii=pinyin_ascii)
        if trad != name:
            endpoints.append(("wikisource_trad", f"https://zh.wikisource.org/wiki/周易/{trad}"))
        return endpoints

    def extract(
        self,
        *,
        html: str,
        api: "TextAPI",
        source_key: str,
        url: str,
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> str:
        title_hints = _build_wikisource_title_hints(url, name or "")
        return _extract_wikisource_text(html, title_hints)


@text_fetcher("ctext_zhs", priority=20)
class CTextZHSFetcher(BaseTextFetcher):
    def build_endpoints(
        self,
        *,
        api: "TextAPI",
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> list[tuple[str, str]]:
        pinyin = api.resolve_pinyin(name=name, index=index, pinyin_ascii=pinyin_ascii)
        if not pinyin:
            return []
        return [("ctext_zhs", f"https://ctext.org/book-of-changes/{pinyin}/zhs")]

    def extract(
        self,
        *,
        html: str,
        api: "TextAPI",
        source_key: str,
        url: str,
        name: Optional[str],
        index: Optional[int],
        pinyin_ascii: Optional[str],
    ) -> str:
        pinyin = _extract_pinyin_from_ctext_url(url) or api.resolve_pinyin(name=name, index=index, pinyin_ascii=pinyin_ascii) or ""
        return _extract_ctext_zhs_text(html, pinyin)


class TextAPI:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        min_delay: float = 0.8,
        max_delay: float = 1.6,
        max_retries: int = 4,
        timeout: float = 15.0,
        user_agents: Optional[list[str]] = None,
        source_names: Optional[list[str]] = None,
        headers_provider=None,
        backoff_provider=None,
        cache_key_builder=None,
    ) -> None:
        self.session = requests.Session()
        self.user_agents = user_agents or DEFAULT_UA_LIST
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.max_retries = int(max_retries)
        self.timeout = float(timeout)
        self._source_names = [s.strip().lower() for s in source_names] if source_names else None
        self._headers_provider = headers_provider
        self._backoff_provider = backoff_provider
        self._cache_key_builder = cache_key_builder
        self._gua_category = GuaCategoryRepository.get()

        root = cache_dir or Path.cwd() / ".cache" / "text_api"
        self.cache_dir = Path(root)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._fetchers = self._build_fetchers()

    def _build_fetchers(self) -> list[BaseTextFetcher]:
        fetchers: list[BaseTextFetcher] = []
        items = sorted(_FETCHER_REGISTRY.items(), key=lambda kv: kv[1].priority)
        for name, cls in items:
            if self._source_names is not None and name not in self._source_names:
                continue
            fetchers.append(cls())
        return fetchers

    def register_fetcher(self, fetcher: BaseTextFetcher, prepend: bool = False) -> None:
        if prepend:
            self._fetchers.insert(0, fetcher)
        else:
            self._fetchers.append(fetcher)

    def _choose_headers(self) -> dict:
        if self._headers_provider:
            return self._headers_provider()
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _backoff(self, attempt: int) -> float:
        if self._backoff_provider:
            return self._backoff_provider(attempt)
        return (2 ** (attempt - 1)) + random.random()

    def _cache_key(self, name: Optional[str], index: Optional[int], pinyin_ascii: Optional[str]) -> str:
        if self._cache_key_builder:
            return self._cache_key_builder(name, index, pinyin_ascii)
        return str(index) if index is not None else (name or pinyin_ascii or "unknown")

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.cache_dir / f"{safe}.txt"

    def resolve_index(self, *, name: Optional[str], index: Optional[int]) -> Optional[int]:
        if index is not None:
            return index
        if not name:
            return None
        for index_key, gua_name in self._gua_category.get("names", {}).items():
            if gua_name == name:
                return int(index_key)
        return None

    def resolve_pinyin(self, *, name: Optional[str], index: Optional[int], pinyin_ascii: Optional[str]) -> Optional[str]:
        if pinyin_ascii:
            return pinyin_ascii
        idx = self.resolve_index(name=name, index=index)
        if idx is None:
            return None
        return self._gua_category.get("pinyin_ascii", {}).get(str(idx))

    def to_traditional_name(self, *, name: str, pinyin_ascii: Optional[str]) -> str:
        mapping = self._gua_category.get("s2t_chars", {})
        if not mapping:
            return name
        if pinyin_ascii and pinyin_ascii in mapping:
            return mapping[pinyin_ascii]
        return "".join(mapping.get(char, char) for char in name)

    def candidate_endpoints(self, *, name: Optional[str], index: Optional[int], pinyin_ascii: Optional[str]) -> list[tuple[str, str]]:
        endpoints: list[tuple[str, str]] = []
        seen = set()
        for fetcher in self._fetchers:
            built = fetcher.build_endpoints(api=self, name=name, index=index, pinyin_ascii=pinyin_ascii)
            for source_key, url in built:
                if url in seen:
                    continue
                seen.add(url)
                endpoints.append((source_key, url))
        return endpoints

    def _candidate_jobs(self, *, name: Optional[str], index: Optional[int], pinyin_ascii: Optional[str]) -> list[tuple[BaseTextFetcher, str, str]]:
        jobs: list[tuple[BaseTextFetcher, str, str]] = []
        seen = set()
        for fetcher in self._fetchers:
            for source_key, url in fetcher.build_endpoints(api=self, name=name, index=index, pinyin_ascii=pinyin_ascii):
                if url in seen:
                    continue
                seen.add(url)
                jobs.append((fetcher, source_key, url))
        return jobs

    def fetch_gua_fulltext_result(
        self,
        name: Optional[str] = None,
        *,
        index: Optional[int] = None,
        pinyin_ascii: Optional[str] = None,
        use_cache: bool = True,
    ) -> FullTextResult:
        resolved_name = name or (self._gua_category.get("names", {}).get(str(index)) if index is not None else None)
        resolved_pinyin = self.resolve_pinyin(name=resolved_name, index=index, pinyin_ascii=pinyin_ascii)

        key = self._cache_key(resolved_name, index, resolved_pinyin)
        cache_file = self._cache_path(key)

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

        jobs = self._candidate_jobs(name=resolved_name, index=index, pinyin_ascii=resolved_pinyin)
        if not jobs:
            raise ValueError("无法确定全文来源，请至少提供 name/index/pinyin_ascii 之一")

        last_exc: Optional[Exception] = None
        for fetcher, source_key, url in jobs:
            for attempt in range(1, self.max_retries + 1):
                try:
                    html = fetcher.fetch(
                        session=self.session,
                        url=url,
                        headers=self._choose_headers(),
                        timeout=self.timeout,
                    )
                    text = fetcher.extract(
                        html=html,
                        api=self,
                        source_key=source_key,
                        url=url,
                        name=resolved_name,
                        index=index,
                        pinyin_ascii=resolved_pinyin,
                    )
                    if not fetcher.validate(text):
                        raise RuntimeError("正文校验失败")

                    try:
                        cache_file.write_text(text, encoding="utf-8")
                    except Exception:
                        pass

                    self._sleep()
                    return FullTextResult(text=text, source_url=url, cache_hit=False, source_key=source_key)
                except Exception as exc:
                    last_exc = exc
                    time.sleep(self._backoff(attempt))

        raise RuntimeError(f"无法获取全文，已尝试: {', '.join(url for _, _, url in jobs)}") from last_exc

    def fetch_gua_fulltext(
        self,
        name: Optional[str] = None,
        *,
        index: Optional[int] = None,
        pinyin_ascii: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        return self.fetch_gua_fulltext_result(
            name=name,
            index=index,
            pinyin_ascii=pinyin_ascii,
            use_cache=use_cache,
        ).text


def _extract_wikisource_text(html: str, title_hints: list[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    lines = text.splitlines()

    idx1 = _find_first_matching_line(lines, title_hints)
    idx_scripture = _find_scripture_marker(lines)
    idx2 = _find_line_index(lines, "隐私政策")
    if idx2 < 0:
        idx2 = _find_line_index(lines, "隱私政策")

    start = idx1
    if idx_scripture >= 0:
        name_idx = _find_previous_nonempty_line(lines, idx_scripture, lookback=6)
        start = name_idx if name_idx >= 0 else max(0, idx_scripture - 2)

    if start >= 0 and idx2 > start:
        text = "\n".join(lines[start : max(start + 1, idx2 - 17)])
    else:
        text = "\n".join(lines)

    text = text.replace("\n\n", "\n").strip()
    return _clean_text_block(text)


def _extract_ctext_zhs_text(html: str, pinyin_ascii: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    lines = text.splitlines()

    idx1 = _find_line_index(lines, "中国哲学书电子化计划")
    idx2 = _find_line_index(lines, f"URN: ctp:book-of-changes/{pinyin_ascii}")

    if idx1 >= 0 and idx2 > idx1:
        text = "\n".join(lines[idx1 + 8 : idx2]).strip()
    else:
        text = "\n".join(lines)

    text = text.replace("打开字典显示相似段落", "")
    text = text.replace("打开字典", "")
    text = text.replace("相关讨论", "")
    return _clean_text_block(text)


def _extract_pinyin_from_ctext_url(url: str) -> str:
    match = re.search(r"book-of-changes/([^/]+)/zhs", url)
    if match:
        return match.group(1)
    return ""


def _build_wikisource_title_hints(url: str, fallback_title: str) -> list[str]:
    hints: list[str] = []
    if fallback_title:
        hints.append(fallback_title)

    parsed = urlparse(url)
    path = unquote(parsed.path)
    marker = "/wiki/周易/"
    if marker in path:
        title = path.split(marker, 1)[1].strip()
        if title and title not in hints:
            hints.append(title)
    return hints


def _find_first_matching_line(lines: list[str], title_hints: list[str]) -> int:
    for target in title_hints:
        idx = _find_line_index(lines, target)
        if idx >= 0:
            return idx

    for target in title_hints:
        if not target:
            continue
        for idx, line in enumerate(lines):
            if target in line.strip():
                return idx
    return -1


def _find_scripture_marker(lines: list[str]) -> int:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("易經：", "易经："):
            return idx
    return -1


def _find_previous_nonempty_line(lines: list[str], index: int, lookback: int = 6) -> int:
    start = max(0, index - lookback)
    for idx in range(index - 1, start - 1, -1):
        if lines[idx].strip():
            return idx
    return -1


def _find_line_index(lines: list[str], target: str) -> int:
    for idx, line in enumerate(lines):
        if line.strip() == target:
            return idx
    return -1


def _clean_text_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    out: list[str] = []
    last_empty = False
    for line in lines:
        if not line.strip():
            if not last_empty:
                out.append("")
            last_empty = True
            continue
        out.append(line)
        last_empty = False
    return "\n".join(out)

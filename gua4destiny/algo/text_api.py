"""Utilities for fetching full text of gua pages (zh.wikisource).

Features:
- requests.Session with rotating User-Agent headers
- polite rate limiting with jitter
- retry with exponential backoff and jitter
- small file cache under .cache/text_api for basic local reuse
- HTML parsing using BeautifulSoup (expects bs4 installed)

Usage:
    from gua4destiny.algo.text_api import TextAPI
    api = TextAPI()
    text = api.fetch_gua_fulltext("乾")
"""
from __future__ import annotations

import random
import time
import json
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_UA_LIST = [
    # A small list of modern-ish UAs to rotate
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36",
]


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

    def _choose_headers(self) -> dict:
        ua = random.choice(self.user_agents)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _polite_sleep(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def _cache_path(self, name: str) -> Path:
        safe = name.replace("/", "_")
        return self.cache_dir / f"{safe}.txt"

    def fetch_gua_fulltext(self, name: str, use_cache: bool = True) -> str:
        """Fetch fulltext for a gua page from zh.wikisource (周易/<name>).

        Returns cleaned plain text. Will cache results to avoid repeated network calls.
        """
        cache_file = self._cache_path(name)
        if use_cache and cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except Exception:
                pass

        url = f"https://zh.wikisource.org/wiki/周易/{name}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = self._choose_headers()
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
                # Basic status check
                resp.raise_for_status()
                html = resp.text
                text = self._extract_main_text(html, name)
                # Save to cache best-effort
                try:
                    cache_file.write_text(text, encoding="utf-8")
                except Exception:
                    pass
                # Polite pause after success
                self._polite_sleep()
                return text
            except Exception as exc:  # requests.RequestException or parsing errors
                last_exc = exc
                backoff = (2 ** (attempt - 1)) + random.random()
                time.sleep(backoff)
                continue

        raise RuntimeError(f"无法获取页面 {url}") from last_exc

    def _extract_main_text(self, html: str, title: str) -> str:
        """Try to extract a readable main body from the page HTML.

        Strategy:
        - Prefer `div#mw-content-text` or `.mw-parser-output` if present.
        - Otherwise fall back to whole-text and heuristics (like test_wikition did).
        """
        soup = BeautifulSoup(html, "html.parser")

        content = None
        # Common MediaWiki containers
        content = soup.find(id="mw-content-text") or soup.find(class_="mw-parser-output")

        if content:
            # Remove script/style/navigation elements
            for bad in content.select("script, style, .mw-editsection, .navbox, table.toc"):
                bad.decompose()

            texts = content.get_text(separator="\n")
            cleaned = _clean_text_block(texts)
            # Heuristic: if it contains the title near the start, trim from there
            idx = cleaned.find(title)
            if idx >= 0:
                cleaned = cleaned[idx:]
            return cleaned.strip()

        # Fallback similar to test_wikition: full page text and slicing
        full = soup.get_text(separator="\n")
        cleaned = _clean_text_block(full)
        # try to slice around title and a footer indicator if possible
        try:
            lines = cleaned.splitlines()
            idx1 = next(i for i, l in enumerate(lines) if title in l)
            # find likely footer marker
            idx2 = next((i for i, l in enumerate(lines[idx1 + 1 :], start=idx1 + 1) if "隐私政策" in l or "隱私政策" in l), len(lines))
            return "\n".join(lines[idx1:idx2]).strip()
        except StopIteration:
            return cleaned.strip()


def _clean_text_block(text: str) -> str:
    # Collapse multiple blank lines and trim
    lines = [l.rstrip() for l in text.splitlines()]
    # remove leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    out_lines = []
    empty = False
    for l in lines:
        if not l.strip():
            if not empty:
                out_lines.append("")
            empty = True
            continue
        out_lines.append(l)
        empty = False
    return "\n".join(out_lines)

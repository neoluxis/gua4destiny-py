from __future__ import annotations

import argparse

try:
    from gua4destiny.algo import BaseTextFetcher, TextAPI, text_fetcher
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from gua4destiny.algo import BaseTextFetcher, TextAPI, text_fetcher


def custom_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def short_backoff(attempt: int) -> float:
    return 0.5 * attempt


def prefer_ctext(name, index, pinyin_ascii):
    if pinyin_ascii:
        return [("custom_ctext_first", f"https://ctext.org/book-of-changes/{pinyin_ascii}/zh")]
    return []


@text_fetcher("demo_backup", priority=50)
class DemoBackupFetcher(BaseTextFetcher):
    def build_endpoints(self, *, api, name, index, pinyin_ascii):
        if name:
            return [("demo_wikisource_backup", f"https://zh.wikisource.org/wiki/周易/{name}")]
        return []

    def extract(self, *, html, api, source_key, url, name, index, pinyin_ascii):
        return html


def run_demo() -> None:
    api = TextAPI(
        min_delay=0.5,
        max_delay=1.0,
        source_names=["wikisource", "ctext_zhs", "demo_backup"],
        headers_provider=custom_headers,
        backoff_provider=short_backoff,
    )

    candidates = api.candidate_endpoints(name="乾", index=0, pinyin_ascii="qian")
    source_keys = [source_key for source_key, _ in candidates]
    print("候选源:", source_keys)
    assert "ctext_zhs" in source_keys, "未找到 ctext_zhs 源"


def run_fetch_demo() -> None:
    api = TextAPI(
        min_delay=0.5,
        max_delay=1.0,
        source_names=["wikisource", "ctext_zhs", "demo_backup"],
        headers_provider=custom_headers,
        backoff_provider=short_backoff,
    )

    result = api.fetch_gua_fulltext_result(name="乾", pinyin_ascii="qian", use_cache=True)
    print("命中源:", result.source_key, result.source_url, result.cache_hit)
    print(result.text[:120])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TextAPI custom source demo")
    parser.add_argument("--fetch", action="store_true", help="执行真实抓取（需要外网）")
    args = parser.parse_args()

    run_demo()
    if args.fetch:
        run_fetch_demo()

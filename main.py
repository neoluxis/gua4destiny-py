#!/usr/bin/env python3
"""启动脚本：通过 `python main.py --host 127.0.0.1 --port 8000` 启动 FastAPI 后端。

示例：
    python main.py --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Gua4Destiny FastAPI server with uvicorn.")
    p.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    p.add_argument("--reload", action="store_true", help="Enable auto-reload (for development)")
    p.add_argument("--workers", type=int, default=1, help="Number of worker processes (uvicorn) to run")
    p.add_argument("--log-level", default="info", help="Uvicorn log level (debug, info, warning, error)")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    try:
        import uvicorn
    except Exception as e:  # pragma: no cover - runtime dependency
        raise RuntimeError("uvicorn is required to run the server. Install it in your environment.") from e

    # Use string app import so uvicorn can spawn workers correctly
    app_location = "gua4destiny.fastapi.app:app"
    # Check that critical runtime dependencies exist before attempting to import the app
    try:
        import fastapi  # type: ignore
    except ModuleNotFoundError:
        import sys

        msg = (
            "Missing required package 'fastapi'.\n"
            "Install project dependencies into your active virtualenv, for example:\n\n"
            "  source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n\n"
            "Or install fastapi directly:\n\n"
            "  pip install fastapi uvicorn\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    try:
        uvicorn.run(
            app_location,
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=max(1, int(args.workers)),
            log_level=args.log_level,
        )
    except ModuleNotFoundError as e:
        # If uvicorn tries to import the app and a dependency is missing, show actionable guidance
        import sys

        print("Failed to import application modules. Missing dependency:", e.name, file=sys.stderr)
        print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

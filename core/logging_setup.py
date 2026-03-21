from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> Path:
    import os, sys
    # 배포 환경에서는 AppData에 로그 저장 (Program Files 쓰기 금지)
    if getattr(sys, 'frozen', False):
        log_dir = Path(os.environ.get("APPDATA", "")) / "Grimoire" / "logs"
    else:
        log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    root = logging.getLogger()
    if any(getattr(handler, "_eso_tool_log", False) for handler in root.handlers):
        return log_path

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler._eso_tool_log = True  # type: ignore[attr-defined]

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    logging.getLogger(__name__).info("logging initialized: %s", log_path)
    return log_path

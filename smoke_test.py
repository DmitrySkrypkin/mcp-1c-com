"""Быстрая проверка COM без MCP (stdio)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Settings
from onec_com import OneCConnection, to_json


def main() -> int:
    settings = Settings.from_env()
    print("Connecting:", settings.connection_string(mask_password=True))
    onec = OneCConnection(settings)
    try:
        print(to_json(onec.connection_info()))
        print("---")
        sample = onec.execute_query(
            "ВЫБРАТЬ ПЕРВЫЕ 3 Код, Наименование ИЗ Справочник.Валюты",
            limit=3,
        )
        print(to_json(sample))
    finally:
        onec.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

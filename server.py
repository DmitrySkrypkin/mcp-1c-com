"""MCP-сервер 1С через COM (V83.COMConnector).

Инструменты:
  - connection_info  — проверка соединения и версия конфигурации
  - execute_query    — язык запросов 1С
  - list_metadata    — список объектов метаданных по виду
  - describe_object  — реквизиты / ТЧ / измерения объекта
"""

from __future__ import annotations

import os
import sys
from typing import Any

# Чтобы импорты работали при запуске по полному пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from config import Settings
from onec_com import OneCConnection, to_json

settings = Settings.from_env()
onec = OneCConnection(settings)

_server_name = os.environ.get("ONEC_MCP_NAME") or (
    f"{settings.ref}-com" if settings.ref else "1c-com"
)
_label = settings.ref or settings.file_path or "1С"

mcp = FastMCP(
    _server_name,
    instructions=(
        f"MCP к базе 1С ({_label}) через COM. "
        "Для выборок используй execute_query на языке запросов 1С. "
        "Ссылки возвращаются как UUID — для читаемых значений добавляй ПРЕДСТАВЛЕНИЕ(...). "
        "Только чтение данных запросами; проведение документов не выполняй."
    ),
)


@mcp.tool()
def connection_info() -> str:
    """Проверить COM-соединение с ИБ и вернуть имя/версию конфигурации."""
    return to_json(onec.connection_info())


@mcp.tool()
def execute_query(
    query_text: str,
    params: dict[str, Any] | None = None,
    limit: int = 500,
) -> str:
    """Выполнить запрос на языке запросов 1С и вернуть строки.

    Args:
        query_text: Текст запроса (ВЫБРАТЬ ...).
        params: Параметры запроса, например {"Дата": "2024-01-01"}.
        limit: Максимум строк в ответе (1..5000).
    """
    return to_json(onec.execute_query(query_text, params=params, limit=limit))


@mcp.tool()
def list_metadata(kind: str = "catalogs") -> str:
    """Список объектов метаданных указанного вида.

    Args:
        kind: catalogs | documents | information_registers | accumulation_registers |
              accounting_registers | enums | charts_of_accounts |
              charts_of_characteristic_types | business_processes | tasks |
              exchange_plans | constants | common_modules | reports | data_processors
    """
    return to_json(onec.list_metadata(kind))


@mcp.tool()
def describe_object(full_name: str) -> str:
    """Описать объект метаданных: реквизиты, табличные части, измерения, ресурсы.

    Args:
        full_name: Полное имя, например "Справочник.Номенклатура"
                   или "Документ.ПоступлениеТоваровУслуг".
    """
    return to_json(onec.describe_object(full_name))


if __name__ == "__main__":
    mcp.run(transport="stdio")

"""Доступ к 1С через V83.COMConnector: соединение, запросы, метаданные."""

from __future__ import annotations

import datetime as dt
import json
import threading
from typing import Any

import win32com.client

from config import Settings

_EMPTY_DATE = dt.datetime(1, 1, 1)

_KIND_MAP = {
    "catalogs": "Catalogs",
    "documents": "Documents",
    "information_registers": "InformationRegisters",
    "accumulation_registers": "AccumulationRegisters",
    "accounting_registers": "AccountingRegisters",
    "enums": "Enums",
    "charts_of_accounts": "ChartsOfAccounts",
    "charts_of_characteristic_types": "ChartsOfCharacteristicTypes",
    "business_processes": "BusinessProcesses",
    "tasks": "Tasks",
    "exchange_plans": "ExchangePlans",
    "constants": "Constants",
    "common_modules": "CommonModules",
    "reports": "Reports",
    "data_processors": "DataProcessors",
}


class OneCConnection:
    """Потокобезопасная обёртка: COM 1С привязан к потоку создания."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        self._thread_id: int | None = None
        self._connector = None
        self._connection = None

    def _ensure(self) -> Any:
        tid = threading.get_ident()
        if self._connection is not None and self._thread_id == tid:
            return self._connection
        if self._connection is not None and self._thread_id != tid:
            raise RuntimeError(
                "COM-соединение 1С можно использовать только из потока, "
                "в котором оно создано."
            )
        self._connector = win32com.client.Dispatch(self._settings.com_connector)
        self._connection = self._connector.Connect(self._settings.connection_string())
        self._thread_id = tid
        return self._connection

    def close(self) -> None:
        with self._lock:
            self._connection = None
            self._connector = None
            self._thread_id = None

    def connection_info(self) -> dict[str, Any]:
        with self._lock:
            conn = self._ensure()
            meta = conn.Metadata
            info: dict[str, Any] = {
                "connection": self._settings.connection_string(mask_password=True),
                "configuration_name": str(meta.Name),
                "configuration_synonym": _presentation(meta),
                "configuration_version": str(meta.Version),
            }
            try:
                info["compatibility_mode"] = str(meta.CompatibilityMode)
            except Exception:
                pass
            try:
                info["platform"] = str(conn.НомерВерсииПлатформы)
            except Exception:
                try:
                    info["platform"] = str(conn.AppVersion)
                except Exception:
                    pass
            return info

    def execute_query(
        self,
        query_text: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        row_limit = limit if limit is not None else self._settings.query_row_limit
        row_limit = max(1, min(int(row_limit), 5000))

        with self._lock:
            conn = self._ensure()
            query = conn.NewObject("Query")
            query.Text = query_text
            if params:
                for key, value in params.items():
                    query.SetParameter(key, _to_1c_value(conn, value))

            result = query.Execute()
            selection = result.Select()
            columns = [_col_name(result, i) for i in range(result.Columns.Count())]
            rows: list[dict[str, Any]] = []
            truncated = False
            while selection.Next():
                if len(rows) >= row_limit:
                    truncated = True
                    break
                row = {col: _from_1c_value(selection.Get(i)) for i, col in enumerate(columns)}
                rows.append(row)

            return {
                "columns": columns,
                "row_count": len(rows),
                "truncated": truncated,
                "limit": row_limit,
                "rows": rows,
            }

    def list_metadata(self, kind: str) -> dict[str, Any]:
        key = kind.strip().lower()
        if key not in _KIND_MAP:
            raise ValueError(
                f"Неизвестный kind={kind!r}. Допустимо: {', '.join(sorted(_KIND_MAP))}"
            )
        collection_name = _KIND_MAP[key]
        with self._lock:
            conn = self._ensure()
            collection = getattr(conn.Metadata, collection_name)
            items = []
            for i in range(collection.Count()):
                obj = collection.Get(i)
                items.append(
                    {
                        "name": str(obj.Name),
                        "full_name": str(obj.FullName()),
                        "synonym": _presentation(obj),
                    }
                )
            items.sort(key=lambda x: x["name"])
            return {"kind": key, "count": len(items), "items": items}

    def describe_object(self, full_name: str) -> dict[str, Any]:
        with self._lock:
            conn = self._ensure()
            meta_obj = conn.Metadata.FindByFullName(full_name)
            if meta_obj is None:
                raise ValueError(f"Объект метаданных не найден: {full_name}")

            info: dict[str, Any] = {
                "full_name": str(meta_obj.FullName()),
                "name": str(meta_obj.Name),
                "synonym": _presentation(meta_obj),
            }

            attrs = _safe_collection(meta_obj, "Attributes")
            if attrs is not None:
                info["attributes"] = [_describe_attr(a) for a in attrs]

            dimensions = _safe_collection(meta_obj, "Dimensions")
            if dimensions is not None:
                info["dimensions"] = [_describe_attr(a) for a in dimensions]

            resources = _safe_collection(meta_obj, "Resources")
            if resources is not None:
                info["resources"] = [_describe_attr(a) for a in resources]

            tabular = _safe_collection(meta_obj, "TabularSections")
            if tabular is not None:
                sections = []
                for ts in tabular:
                    sections.append(
                        {
                            "name": str(ts.Name),
                            "synonym": _presentation(ts),
                            "attributes": [
                                _describe_attr(a)
                                for a in _safe_collection(ts, "Attributes") or []
                            ],
                        }
                    )
                info["tabular_sections"] = sections

            return info


def _presentation(meta_obj: Any) -> str:
    try:
        syn = meta_obj.Synonym
        if syn is not None:
            try:
                return str(syn.Get())
            except Exception:
                return str(syn)
    except Exception:
        pass
    return str(meta_obj.Name)


def _safe_collection(obj: Any, name: str) -> list[Any] | None:
    try:
        coll = getattr(obj, name)
    except Exception:
        return None
    if coll is None:
        return None
    try:
        count = coll.Count()
    except Exception:
        return None
    return [coll.Get(i) for i in range(count)]


def _describe_attr(attr: Any) -> dict[str, Any]:
    item = {
        "name": str(attr.Name),
        "synonym": _presentation(attr),
        "type": _type_description(attr),
    }
    return item


def _type_description(attr: Any) -> str:
    try:
        types = attr.Type.Types()
        parts = []
        for i in range(types.Count()):
            t = types.Get(i)
            try:
                parts.append(str(t))
            except Exception:
                parts.append("?")
        return ", ".join(parts) if parts else "примитив"
    except Exception:
        return "примитив"


def _col_name(result: Any, index: int) -> str:
    col = result.Columns.Get(index)
    try:
        name = str(col.Name)
        if name:
            return name
    except Exception:
        pass
    return f"Col{index}"


def _to_1c_value(conn: Any, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        # ISO date / datetime
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            try:
                d = dt.date.fromisoformat(value)
                return dt.datetime(d.year, d.month, d.day)
            except ValueError:
                pass
        if "T" in value or (len(value) > 10 and value[4] == "-"):
            try:
                return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError:
                pass
        return value
    return value


def _from_1c_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dt.datetime):
        if value <= _EMPTY_DATE:
            return None
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, dt.date):
        if value.year <= 1:
            return None
        return value.isoformat()
    # COM-ссылки / объекты → UUID или строка
    try:
        uuid = value.UUID()
        return str(uuid)
    except Exception:
        pass
    try:
        return str(value)
    except Exception:
        return repr(value)


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)

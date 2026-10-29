"""Сборка строки соединения 1С из переменных окружения."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


def _q(value: str) -> str:
    return value.replace('"', '""')


@dataclass
class Settings:
    com_connector: str
    raw_connection_string: str | None
    file_path: str | None
    server: str | None
    ref: str | None
    user: str | None
    password: str | None
    query_row_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        limit_raw = os.environ.get("ONEC_QUERY_LIMIT", "500")
        try:
            limit = max(1, min(int(limit_raw), 5000))
        except ValueError:
            limit = 500
        return cls(
            com_connector=os.environ.get("ONEC_COMCONNECTOR", "V83.COMConnector"),
            raw_connection_string=os.environ.get("ONEC_CONNECTION_STRING"),
            file_path=os.environ.get("ONEC_FILE"),
            server=os.environ.get("ONEC_SRVR"),
            ref=os.environ.get("ONEC_REF"),
            user=os.environ.get("ONEC_USR"),
            password=os.environ.get("ONEC_PWD"),
            query_row_limit=limit,
        )

    def connection_string(self, mask_password: bool = False) -> str:
        if self.raw_connection_string:
            s = self.raw_connection_string
            if mask_password:
                s = re.sub(
                    r'(Pwd\s*=\s*)"[^"]*"',
                    r'\1"***"',
                    s,
                    flags=re.IGNORECASE,
                )
            return s

        parts: list[str] = []
        if self.file_path:
            parts.append(f'File="{_q(self.file_path)}"')
        elif self.server and self.ref:
            parts.append(f'Srvr="{_q(self.server)}"')
            parts.append(f'Ref="{_q(self.ref)}"')
        else:
            raise ValueError(
                "Не задано соединение. Укажите ONEC_CONNECTION_STRING, "
                "либо ONEC_FILE, либо ONEC_SRVR + ONEC_REF."
            )

        if self.user:
            parts.append(f'Usr="{_q(self.user)}"')
        if self.password:
            pwd = "***" if mask_password else _q(self.password)
            parts.append(f'Pwd="{pwd}"')
        return ";".join(parts)

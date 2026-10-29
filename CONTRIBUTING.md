# Contributing

Issues и pull requests приветствуются.

## Локальная разработка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python smoke_test.py
```

Перед PR:

- не добавляйте пароли, строки соединения, дампы ИБ;
- сохраняйте совместимость с Windows PowerShell 5.1 в `.ps1`;
- держите зависимость `mcp` в диапазоне `>=1.9,<2` (FastMCP API v1), пока не будет явной миграции на mcp 2.x.

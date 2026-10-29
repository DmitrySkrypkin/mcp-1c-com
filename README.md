# mcp-1c-com

**MCP-сервер для 1С:Предприятие через COM** — Cursor / Claude / другие MCP-клиенты получают доступ к данным информационной базы **без расширений и без правки конфигурации**.

Работает с УПП, КА, УТ, ERP и любыми другими конфигурациями на платформе 8.3 (Windows).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%2B%201C%208.3-blue.svg)](#требования)
[![Python](https://img.shields.io/badge/python-3.10%2B%20x64-yellow.svg)](#установка)
[![MCP](https://img.shields.io/badge/MCP-stdio-purple.svg)](https://modelcontextprotocol.io/)

---

## Зачем это нужно

Типовой путь «MCP как расширение 1С» (HTTP-сервис в `.cfe`) **не работает** на старых режимах совместимости — например УПП 1.3 с режимом **8.2.13** не умеет хранить расширения.

Этот проект обходит ограничение:

```text
AI-клиент  →  MCP (stdio)  →  Python  →  V83.COMConnector  →  ИБ 1С
```

В конфигурацию **ничего не ставится**. Нужны только Windows, платформа 1С и доступ к базе.

| Подход | Меняет конфигурацию | УПП 8.2.13 | Запросы к данным |
|--------|---------------------|------------|------------------|
| Расширение + HTTP (`1c_mcp` и аналоги) | да (`.cfe`) | часто нельзя | да |
| **mcp-1c-com (этот проект)** | **нет** | **да** | **да** |
| MCP только по XML-выгрузке | нет | да | нет (только код/метаданные) |

---

## Возможности

| Tool | Назначение |
|------|------------|
| `connection_info` | Проверка соединения, имя и версия конфигурации |
| `execute_query` | Язык запросов 1С (`ВЫБРАТЬ …`), параметры, лимит строк |
| `list_metadata` | Справочники, документы, регистры и др. |
| `describe_object` | Реквизиты, ТЧ, измерения, ресурсы объекта |

Несколько баз = несколько MCP-серверов в `.cursor/mcp.json` (один и тот же `server.py`, разные `ONEC_*`).

---

## Требования

- Windows x64
- 1С:Предприятие 8.3 (зарегистрированный `V83.COMConnector` / `comcntr.dll`)
- Python 3.10+ **той же разрядности**, что `comcntr.dll` (обычно x64)
- Права пользователя ИБ на внешнее соединение и чтение нужных данных

---

## Быстрый старт

### 1. Клонировать и поставить зависимости

```powershell
git clone https://github.com/<OWNER>/mcp-1c-com.git
cd mcp-1c-com

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Зарегистрировать COM (один раз, от администратора)

```powershell
regsvr32 "C:\Program Files\1cv8\8.3.<build>\bin\comcntr.dll"
```

### 3. Проверить соединение

```powershell
$env:ONEC_SRVR = "localhost"
$env:ONEC_REF  = "UPP"
$env:ONEC_USR  = "User"
$env:ONEC_PWD  = "secret"
python smoke_test.py
```

### 4. Подключить к Cursor

В корне **вашего** проекта создайте `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "upp-com": {
      "command": "C:\\path\\to\\mcp-1c-com\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\mcp-1c-com\\server.py"],
      "env": {
        "ONEC_MCP_NAME": "upp-com",
        "ONEC_SRVR": "localhost",
        "ONEC_REF": "UPP",
        "ONEC_USR": "User",
        "ONEC_PWD": "secret"
      }
    }
  }
}
```

Готовый шаблон на две базы: [`examples/mcp.json.example`](examples/mcp.json.example).

Перезапустите MCP в Cursor (**Settings → MCP → Refresh**).

---

## Инсталлятор в другой проект

Скрипт ставит portable Python (если нужно), зависимости, регистрирует COM, пишет `.cursor/mcp.json`:

```powershell
cd mcp-1c-com

# Интерактивно
.\Install-Mcp1cCom.ps1 -ProjectPath D:\MyProject -Interactive

# Или сразу параметрами
.\Install-Mcp1cCom.ps1 `
  -ProjectPath D:\MyProject `
  -ServerName ka-com `
  -Srvr localhost `
  -Ref KA `
  -User User `
  -Password 'secret'
```

Флаги:

| Параметр | Смысл |
|----------|--------|
| `-CopyIntoProject` | Скопировать код сервера в `Project\tools\mcp-1c-com` |
| `-SharedServerDir` | Не копировать — указать общий каталог с `server.py` |
| `-SkipComRegister` | Не вызывать `regsvr32` |
| `-SkipSmokeTest` | Не проверять соединение |
| `-PythonDir` | Куда класть/искать portable Python |

Пароли пишутся только в `.cursor/mcp.json` (его стоит держать в `.gitignore`).

---

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `ONEC_SRVR` + `ONEC_REF` | Серверная база |
| `ONEC_FILE` | Файловая база |
| `ONEC_CONNECTION_STRING` | Готовая строка соединения (приоритет) |
| `ONEC_USR` / `ONEC_PWD` | Пользователь / пароль |
| `ONEC_MCP_NAME` | Имя сервера в MCP |
| `ONEC_COMCONNECTOR` | ProgID, по умолчанию `V83.COMConnector` |
| `ONEC_QUERY_LIMIT` | Лимит строк по умолчанию (1…5000) |

---

## Примеры запросов

Количество элементов номенклатуры:

```bsl
ВЫБРАТЬ КОЛИЧЕСТВО(Ссылка) КАК Количество
ИЗ Справочник.Номенклатура
```

С представлением ссылок:

```bsl
ВЫБРАТЬ ПЕРВЫЕ 20
  Номер,
  Дата,
  ПРЕДСТАВЛЕНИЕ(Контрагент) КАК Контрагент
ИЗ Документ.РеализацияТоваровУслуг
УПОРЯДОЧИТЬ ПО Дата УБЫВ
```

---

## Архитектура

```mermaid
flowchart LR
  A[Cursor / Claude] -->|MCP stdio| B[server.py]
  B --> C[onec_com.py]
  C -->|V83.COMConnector| D[(ИБ 1С)]
```

Подробнее: [`docs/architecture.md`](docs/architecture.md).

---

## Безопасность

- Сервер рассчитан на **чтение** через язык запросов. Не давайте агенту учётку с лишними правами.
- Не коммитьте `.cursor/mcp.json` с паролями.
- COM открывает полноценный сеанс 1С от имени указанного пользователя — относитесь к этому как к доступу к базе.

---

## Ограничения

- Только **Windows** (COM).
- Совпадение разрядности Python ↔ `comcntr.dll`.
- Ссылки в результате запроса приходят как **UUID** — для читаемых значений используйте `ПРЕДСТАВЛЕНИЕ(...)`.
- Произвольный `Выполнить`/`Вычислить` через внешнее соединение недоступен (это ограничение платформы).

---

## Устранение неполадок

**`Библиотека не зарегистрирована` / нет метода `Connect`**  
Повторно зарегистрируйте `comcntr.dll` от администратора.

**`Класс не зарегистрирован` (0x80040154)**  
Не тот `comcntr.dll` или другая разрядность Python.

**Несколько версий платформы**  
`V83.COMConnector` указывает на последнюю зарегистрированную. Выполните `regsvr32` для нужной сборки.

---

## Структура репозитория

```text
mcp-1c-com/
├── server.py              # MCP stdio (FastMCP)
├── onec_com.py            # COM: запросы и метаданные
├── config.py              # Строка соединения из env
├── smoke_test.py          # Проверка без Cursor
├── Install-Mcp1cCom.ps1   # Инсталлятор в проект
├── requirements.txt
├── examples/
│   └── mcp.json.example
└── docs/
    └── architecture.md
```

---

## Лицензия

[MIT](LICENSE)

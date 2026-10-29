# AGENTS.md — установка mcp-1c-com силами ИИ

Инструкция для AI-агента (Cursor, Claude Code и т.п.).  
Цель: подключить MCP к живой базе **1С:Предприятие 8.3** через COM **без изменения конфигурации**.

Читай этот файл целиком перед действиями. Не импровизируй обходы через расширения 1С.

---

## 0. Контекст (что это)

| | |
|--|--|
| Репозиторий | https://github.com/DmitrySkrypkin/mcp-1c-com |
| Транспорт | MCP stdio |
| Связь с 1С | `V83.COMConnector` (Windows COM) |
| Меняет конфигурацию 1С? | **Нет** |
| Платформа | Только **Windows** + **1С 8.3** |
| 1С 7.7 | **Не поддерживается** |

Tools после установки: `connection_info`, `execute_query`, `list_metadata`, `describe_object`.

---

## 1. Спроси у пользователя (обязательно)

Не продолжай без ответов:

1. **Путь к проекту Cursor**, куда ставить MCP (каталог с `.cursor/` или корень репо).
2. Тип ИБ:
   - серверная: `Srvr` + `Ref`, или
   - файловая: полный путь к каталогу базы.
3. **Пользователь и пароль** 1С (с правом внешнего соединения / чтения).
4. Желаемое **имя MCP-сервера** в Cursor (например `upp-com`, `ka-com`). Если не указано — `{Ref}-com` в нижнем регистре.
5. Нужно ли подключить **несколько баз** (тогда повтори шаги 4–7 для каждой).

Секреты пиши только в `.cursor/mcp.json`. **Никогда** не коммить пароли, не печатай их в README/issues.

---

## 2. Предусловия на машине

Проверь и зафиксируй результат:

```powershell
# Разрядность процесса (нужен x64 под типичный comcntr.dll)
[Environment]::Is64BitOperatingSystem
[Environment]::Is64BitProcess

# Платформа 1С
Get-ChildItem "C:\Program Files\1cv8" -ErrorAction SilentlyContinue | Select-Object Name
Test-Path "C:\Program Files\1cv8\*\bin\comcntr.dll"

# COM-класс
reg query "HKCR\V83.COMConnector" 2>$null

# Python (если есть)
where.exe python 2>$null
```

Если `V83.COMConnector` нет или `Connect` падает с «библиотека не зарегистрирована» — зарегистрируй (нужны права администратора):

```powershell
regsvr32 "C:\Program Files\1cv8\<версия>\bin\comcntr.dll"
```

Если пользователь не может повысить права — остановись и попроси зарегистрировать COM вручную.

---

## 3. Получить код сервера

Предпочтительный вариант — клон рядом с проектами или в `tools`:

```powershell
git clone https://github.com/DmitrySkrypkin/mcp-1c-com.git "D:\mcp-1c-com"
```

Альтернатива: скопировать в `<Project>\tools\mcp-1c-com` файлы:

- `server.py`, `onec_com.py`, `config.py`, `smoke_test.py`
- `requirements.txt`, `Install-Mcp1cCom.ps1`, `.env.example`

Не копируй `_python/`, `.venv/`, `.cursor/mcp.json` с чужими паролями.

---

## 4. Python и зависимости

**Вариант A — инсталлятор (предпочтительно на Windows без системного Python):**

```powershell
cd D:\mcp-1c-com
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Mcp1cCom.ps1 `
  -ProjectPath "<PROJECT>" `
  -ServerName "<NAME>" `
  -Srvr "<SRVR>" `
  -Ref "<REF>" `
  -User "<USER>" `
  -Password "<PASSWORD>"
```

Для файловой базы вместо `-Srvr`/`-Ref` укажи `-File "<PATH>"`.  
Флаг `-CopyIntoProject` — положить код в проект.  
`-SkipComRegister` — если COM уже ок.  
`-SkipSmokeTest` — только если проверку сделаешь сам.

**Вариант B — вручную:**

```powershell
cd D:\mcp-1c-com
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Важно: пакет `mcp` держать в диапазоне **`>=1.9,<2`** (см. `requirements.txt`). MCP 2.x ломает `FastMCP`.

Если системный MSI Python блокируется политикой — используй embeddable zip (это делает инсталлятор) или уже существующий portable из другого проекта.

Python и `comcntr.dll` должны быть **одной разрядности** (обычно оба x64).

---

## 5. Записать `.cursor/mcp.json`

Путь: `<Project>\.cursor\mcp.json`.  
Если файл уже есть — **добавь** новый ключ в `mcpServers`, не затирая другие серверы.

Шаблон серверной ИБ:

```json
{
  "mcpServers": {
    "<NAME>": {
      "command": "<ABS_PYTHON>",
      "args": ["<ABS_SERVER_PY>"],
      "env": {
        "ONEC_MCP_NAME": "<NAME>",
        "ONEC_SRVR": "<SRVR>",
        "ONEC_REF": "<REF>",
        "ONEC_USR": "<USER>",
        "ONEC_PWD": "<PASSWORD>"
      }
    }
  }
}
```

Файловая ИБ — вместо `ONEC_SRVR`/`ONEC_REF`:

```json
"ONEC_FILE": "C:\\Bases\\MyBase"
```

Либо целиком:

```json
"ONEC_CONNECTION_STRING": "Srvr=\"...\";Ref=\"...\";Usr=\"...\";Pwd=\"...\""
```

Правила путей:

- Только **абсолютные** пути Windows.
- В JSON экранируй `\`: `C:\\Users\\...`.
- `command` = `python.exe` (venv или portable), `args[0]` = полный путь к `server.py`.

Добавь в `.gitignore` проекта (если ещё нет):

```gitignore
.cursor/mcp.json
```

Можно оставить `.cursor/mcp.json.example` **без пароля**.

Готовый пример на две базы: `examples/mcp.json.example`.

---

## 6. Smoke-тест (до Refresh в Cursor)

```powershell
$env:ONEC_SRVR = "<SRVR>"
$env:ONEC_REF  = "<REF>"
$env:ONEC_USR  = "<USER>"
$env:ONEC_PWD  = "<PASSWORD>"
& "<ABS_PYTHON>" "<ABS>\smoke_test.py"
```

Успех:

- печатается имя/версия конфигурации;
- выборка из `Справочник.Валюты` (или понятная ошибка прав, но не COM).

Типичные ошибки:

| Симптом | Действие |
|---------|----------|
| `Библиотека не зарегистрирована` / нет `Connect` | `regsvr32 comcntr.dll` от админа |
| `Класс не зарегистрирован` 0x80040154 | разрядность Python ≠ dll или не тот comcntr |
| Ошибка аутентификации | логин/пароль/имя базы |
| Поле не найдено в запросе smoke | нормально на экзотических конфигах; проверь `connection_info` и свой `ВЫБРАТЬ` |

Не объявляй установку успешной без рабочего smoke или явного `connection_info` через MCP.

---

## 7. Активация в Cursor

1. Сообщи пользователю: **Settings → MCP → Refresh** или перезапуск Cursor.
2. Должен появиться сервер с именем `<NAME>`.
3. Проверь tool `connection_info`.
4. Контрольный запрос:

```bsl
ВЫБРАТЬ КОЛИЧЕСТВО(Ссылка) КАК Количество ИЗ Справочник.Номенклатура
```

(имя справочника может отличаться — при сомнении сначала `list_metadata` с `kind=catalogs`).

---

## 8. Правила работы с данными после установки

- Предпочитай **чтение** через `execute_query`.
- Для читаемых ссылок в запросе используй `ПРЕДСТАВЛЕНИЕ(...)`.
- Ссылки в JSON приходят как UUID — это ожидаемо.
- Не проводи документы и не пиши данные, пока пользователь явно не попросит и не подтвердит права.
- Не путай этот MCP с XML-дампом конфигурации: здесь живая ИБ.
- Не предлагай ставить расширение `1c_mcp` (.cfe), если цель — именно этот COM-путь (особенно на УПП с режимом совместимости 8.2.x).

---

## 9. Несколько информационных баз

Один `server.py` — много записей в `mcpServers` с разным `env` и `ONEC_MCP_NAME`.  
Каждая база = отдельный процесс MCP в Cursor.

---

## 10. Чеклист сдачи пользователю

- [ ] Код получен (клон или copy)
- [ ] Python x64 + `pip install -r requirements.txt` (mcp&lt;2)
- [ ] COM `V83.COMConnector` отвечает
- [ ] `.cursor/mcp.json` с абсолютными путями
- [ ] `.cursor/mcp.json` в `.gitignore`
- [ ] `smoke_test.py` OK
- [ ] Пользователь сделал Refresh MCP
- [ ] `connection_info` / пробный запрос OK
- [ ] Пароли не попали в git и публичные логи

---

## 11. Краткий one-liner для агента

```text
Clone DmitrySkrypkin/mcp-1c-com → ensure V83 COM + Python x64 →
pip install -r requirements.txt (mcp<2) → write Project/.cursor/mcp.json
with ABS paths and ONEC_* → run smoke_test.py → ask user to Refresh MCP.
Never commit passwords. Not for 1C 7.7. Do not use .cfe extensions for this path.
```

# HH Auto Response

Инструмент для работы с HH.ru: поиск вакансий, скоринг, CRM, генерация сопроводительных писем, review-очередь, browser-assisted отклики, обработка HH-чатов и веб-dashboard.

Репозиторий: https://github.com/gest0r1/hh-auto-response

Проект является форком `Glour/headhunter-crm-agent` и адаптируется под персональный сценарий поиска работы одним пользователем. Внутреннее имя Python-пакета пока сохранено, чтобы не вносить лишние изменения в рабочий код.

## Что умеет

- искать вакансии через публичную HH-выдачу без OAuth;
- работать через HH API при наличии OAuth-приложения и токенов;
- хранить вакансии, отклики, статусы, feedback и run logs в SQLite;
- считать fit-score по профилю кандидата, stop keywords, зарплате, формату и стеку;
- генерировать персонализированные сопроводительные письма;
- вести review queue до отправки;
- открывать HH через Playwright и заполнять формы отклика;
- отправлять отклики только при явно включённых live-gates;
- читать HH-чаты и готовить ответы на screening questions;
- распознавать внешние handoff: Telegram, Google Forms и другие анкеты;
- показывать CRM через FastAPI + React/Vite dashboard;
- использовать Telegram-review бота как дополнительный интерфейс.

## Безопасные ограничения

По умолчанию проект работает в dry-run режиме.

Он не должен:

- обходить CAPTCHA, 403, 429, login-wall или anti-bot;
- автоматически включать live-отправку после установки;
- хранить `.env`, токены, cookies, browser profile или локальную SQLite базу в git;
- отправлять внешние формы с неизвестными обязательными полями, login requirement, file upload или payment.

## Требования

Минимально:

- Linux/macOS или WSL;
- Git;
- Python 3.11+;
- Node.js 22+ и npm — только для dashboard;
- Chromium, устанавливаемый через Playwright.

## Установка

### Вариант 1 — обычная установка из GitHub

```bash
git clone https://github.com/gest0r1/hh-auto-response.git
cd hh-auto-response
bash scripts/install.sh
```

`scripts/install.sh`:

- создаёт `.venv`;
- устанавливает backend, dev и browser dependencies;
- устанавливает Chromium для Playwright;
- создаёт `.env` из `.env.example`, если файла ещё нет;
- создаёт `data/profile.local.json` из шаблона, если файла ещё нет;
- устанавливает зависимости dashboard через `npm ci`, если npm доступен;
- не перезаписывает существующие `.env` и `profile.local.json`.

### Вариант 2 — bootstrap-скрипт

Если репозиторий ещё не клонирован:

```bash
curl -fsSL https://raw.githubusercontent.com/gest0r1/hh-auto-response/main/scripts/install_from_github.sh \
  -o /tmp/install_hh_auto_response.sh
bash /tmp/install_hh_auto_response.sh
```

По умолчанию проект устанавливается в:

```text
$HOME/hh-auto-response
```

Другой каталог можно передать первым аргументом:

```bash
bash /tmp/install_hh_auto_response.sh /opt/hh-auto-response
```

Bootstrap намеренно завершится с ошибкой, если каталог уже существует: он не делает автоматический `git pull` и не перезаписывает локальные изменения.

### Ручная установка без install.sh

```bash
git clone https://github.com/gest0r1/hh-auto-response.git
cd hh-auto-response

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium

cp .env.example .env
cp data/profile.template.json data/profile.local.json

cd dashboard
npm ci
cd ..
```

## Первичная настройка

Открой `.env` и проверь минимум:

```bash
PYTHONPATH=backend
HH_CRM_DB_PATH=./data/hh_crm.sqlite3
HH_PROFILE_PATH=./data/profile.local.json
HH_BROWSER_USER_DATA_DIR=./data/hh-browser-profile
HH_USER_AGENT=hh-auto-response/0.1 (https://github.com/gest0r1/hh-auto-response)
```

`HH_USER_AGENT` должен содержать реальный контакт или URL проекта.

После этого заполни:

```text
data/profile.local.json
```

Основные поля профиля:

- `full_name`;
- `headline`;
- `positioning`;
- `target_roles`;
- `skills`;
- `preferred_keywords`;
- `stop_keywords`;
- `min_monthly_salary`;
- `strengths`;
- `cases`;
- ссылки на портфолио и подтверждающие материалы, если они реально используются.

Личные исходники можно хранить локально в:

```text
data/profile-sources/
data/evidence-packs/
data/private-notes/
```

Эти каталоги исключены из git.

## Первый запуск — только dry-run

```bash
source .venv/bin/activate
export PYTHONPATH=backend

python -m app.cli init-db
python -m app.cli run-public-once \
  --query 'CIO' \
  --query 'IT Director' \
  --query 'CDTO' \
  --per-query 20 \
  --draft-threshold 80

python -m app.cli export-review-queue \
  --output ./data/review_queue.md \
  --min-score 80

python -m app.cli summary
```

На этом этапе никаких откликов отправляться не должно.

## Dashboard

Backend:

```bash
source .venv/bin/activate
PYTHONPATH=backend HH_CRM_DB_PATH=./data/hh_crm.sqlite3 \
  uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Frontend во втором терминале:

```bash
cd dashboard
npm run dev
```

Production build:

```bash
cd dashboard
npm run build
```

## Первый вход в HH через Playwright

Для browser-assisted откликов нужен persistent browser profile:

```bash
source .venv/bin/activate
export PYTHONPATH=backend
python -m app.cli apply-browser-queue \
  --min-score 80 \
  --limit 1 \
  --user-data-dir ./data/hh-browser-profile
```

Первый вход лучше делать не headless:

1. войти в HH вручную;
2. пройти SMS/2FA, если требуется;
3. убедиться, что открываются вакансия и форма отклика;
4. сохранить browser profile для последующих запусков.

## Dry-run автооткликов

```bash
source .venv/bin/activate
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'CIO' \
  --query 'IT Director' \
  --per-query 20 \
  --draft-threshold 85 \
  --min-score 85 \
  --limit 5 \
  --daily-limit 5 \
  --headless
```

Или wrapper:

```bash
bash scripts/run_hh_auto_apply.sh
```

## Live автоотклики

Live submit включается только двойным gate:

```bash
HH_AUTO_APPLY_SEND=1 \
HH_AUTO_APPLY_ALLOW_LIVE_SEND=1 \
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'CIO' \
  --min-score 90 \
  --limit 1 \
  --daily-limit 3 \
  --headless \
  --send
```

Перед первым live-запуском используй минимальный лимит и проверь сгенерированный текст вручную.

Если возникает неправильный отклик, дубль, неверное резюме или плохой шаблон — live режим нужно сразу выключить и вернуть dry-run.

## HH-чаты

Dry-run:

```bash
PYTHONPATH=backend python -m app.cli reply-hh-chats \
  --limit 5 \
  --max-chats 160 \
  --headless
```

Live ответы также защищены двумя флагами:

```bash
HH_CHAT_REPLY_SEND=1 \
HH_CHAT_REPLY_ALLOW_LIVE_SEND=1 \
PYTHONPATH=backend python -m app.cli reply-hh-chats \
  --limit 1 \
  --headless \
  --send
```

Внешние handoff и Google Forms по умолчанию остаются выключенными.

## Telegram-review бот

Создай файл:

```text
.secrets/hh_telegram.env
```

Минимум:

```bash
HH_TELEGRAM_BOT_TOKEN=<token>
HH_TELEGRAM_CHAT_ID=
```

Запуск:

```bash
bash scripts/run_hh_telegram_agent.sh
```

После запуска отправь `/start` боту.

Для установки watchdog/daily cron:

```bash
source .venv/bin/activate
python scripts/install_hh_telegram_cron.py
```

Cron installer вычисляет путь к проекту относительно самого репозитория, поэтому не зависит от имени каталога.

## Cron

Пример dry-run проверки HH-чатов:

```cron
*/10 * * * * /path/to/hh-auto-response/scripts/run_hh_chat_replies_hourly.sh >> /path/to/hh-auto-response/logs/hh_chat_replies.log 2>&1
```

Пример approved live lane:

```cron
*/10 * * * * /path/to/hh-auto-response/scripts/run_hh_chat_replies_live_approved.sh >> /path/to/hh-auto-response/logs/hh_chat_replies.log 2>&1
```

Live cron включай только после проверки dry-run.

## Проверка установки

```bash
source .venv/bin/activate
pytest -q
ruff check backend tests
PYTHONPATH=backend python -m compileall -q backend/app
bash scripts/run_smoke.sh
```

Dashboard отдельно:

```bash
cd dashboard
npm run build
```

## Обновление проекта

```bash
cd ~/hh-auto-response
git status
git pull --ff-only
source .venv/bin/activate
python -m pip install -e '.[dev,browser]'
cd dashboard && npm ci && cd ..
```

Перед `git pull` убедись, что локальные изменения сохранены или закоммичены.

## Что не должно попадать в Git

Не коммить:

- `.env`;
- `.secrets/`;
- `data/profile.local.json`;
- `data/profile-sources/`;
- `data/evidence-packs/`;
- `data/private-notes/`;
- `data/hh_crm.sqlite3`;
- `data/hh-browser-profile/`;
- `data/hh_chat_reply_state.json`;
- logs;
- cookies и tokens;
- screenshots и raw resumes с персональными данными.

## Структура

```text
backend/app/      FastAPI, CLI, scoring, CRM, HH/Playwright logic
dashboard/        React/Vite dashboard
data/             templates и локальные runtime-данные
scripts/          install, run, cron и safety wrappers
tests/            pytest
docs/             архитектура и методики
```

## Лицензия и ответственность

В репозитории сохранена лицензия исходного проекта. Использование кода должно соответствовать условиям лицензии и отдельно полученным разрешениям правообладателя.

Автоматизация работает с пользовательским аккаунтом HH.ru. Не обходи защиту площадки и не включай массовую отправку без предварительной проверки правил отбора, сопроводительных писем и лимитов.

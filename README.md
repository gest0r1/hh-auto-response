# HeadHunter CRM Agent

Полноценный стартовый контур под автоматизацию поиска работы на HH.ru:

- SQLite CRM для вакансий, откликов, фидбэка и learning-сигналов.
- Агент поиска: работает через HH API или no-API режим публичной web-выдачи, считает релевантность, создаёт черновики откликов.
- Генератор персональных сопроводительных сообщений на основе профиля, кейсов и вакансии.
- Самообучение: approve/reject/edit/reply/interview/offer меняют веса ключевых сигналов.
- FastAPI backend.
- React/Vite dashboard с визуальной CRM, воронкой, скорингом и черновиками.

Безопасность по умолчанию: система **не отправляет отклики наружу**. Она ищет, сохраняет, ранжирует и готовит черновики. No-API режим берёт публичные страницы поиска HH и делает review queue со ссылками «Откликнуться». Реальную отправку через OAuth или браузерный сценарий подключаем отдельно только после подтверждения.

## Структура

```text
backend/app/
  api.py          FastAPI endpoints
  agent.py        search/score/draft/learn orchestration
  hh_client.py    HH API client
  hh_public.py    no-API public HH web-search parser/client
  review_export.py markdown review queue export
  scoring.py      deterministic vacancy scoring
  responses.py    cover-letter generator; reads docs/cover-letter-methodology.md
  learning.py     feedback learning loop
  repository.py   SQLite CRM repository
  db.py           schema/init
  telegram_agent.py  isolated Telegram bot for /start, /run, /queue, /summary and inline review actions
  cli.py          local commands

dashboard/       React/Vite visual CRM
docs/            architecture and operating notes
data/            local SQLite DB and profile templates
tests/           pytest coverage for core agent behavior
```

## Быстрый старт

```bash
cd /root/home/headhunter-crm-agent
cp .env.example .env
PYTHONPATH=backend python -m app.cli init-db
PYTHONPATH=backend python -m app.cli seed-demo
PYTHONPATH=backend python -m app.cli run-public-once --query 'React Python CRM' --per-query 10
PYTHONPATH=backend python -m app.cli summary
```

No-API режим после запуска создаёт/обновляет `data/review_queue.md`: там лучшие вакансии, ссылки на карточку/форму отклика и готовые тексты.

Backend API:

```bash
PYTHONPATH=backend HH_CRM_DB_PATH=./data/hh_crm.sqlite3 uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

Dashboard:

```bash
cd dashboard
npm install
npm run dev
```

Production build check:

```bash
cd dashboard
npm run build
```

## No-API режим HH

Если заявку/ключи HH API не делаем, агент работает через обычные публичные страницы `hh.ru/search/vacancy`:

```bash
PYTHONPATH=backend python -m app.cli run-public-once \
  --query 'React Python CRM' \
  --query 'Telegram bot Python' \
  --per-query 20 \
  --draft-threshold 80

PYTHONPATH=backend python -m app.cli export-review-queue --output ./data/review_queue.md --min-score 80

# готовый сценарий с несколькими поисковыми запросами
scripts/run_no_api_agent.sh
```

Что делает no-API pipeline:

1. Загружает публичную web-выдачу HH, не используя `api.hh.ru`.
2. Парсит карточки вакансий, зарплату, удалёнку, компанию и ссылку «Откликнуться».
3. Дедуплицирует в SQLite CRM.
4. Скорит под профиль Александра Олеговича.
5. Генерирует черновики откликов по `docs/cover-letter-methodology.md`.
6. Экспортирует review queue в `data/review_queue.md`.
7. Browser runner может открыть форму отклика, вставить черновик и по флагу `--send` нажать отправку.
8. Auto-apply режим объединяет поиск, скоринг, генерацию черновиков и браузерную отправку в один запуск с дневным лимитом.

Browser runner ставится отдельно, чтобы обычный backend/CI не тянул браузер:

```bash
pip install -e '.[browser]'
python -m playwright install chromium

# первый запуск лучше без --send: войти в HH в открывшемся браузере, проверить вставку текста
PYTHONPATH=backend python -m app.cli apply-browser-queue --min-score 80 --limit 3

# реальная отправка только явным флагом
PYTHONPATH=backend python -m app.cli apply-browser-queue --min-score 80 --limit 3 --send
```

Полный автоматический запуск в один шаг:

```bash
# dry-run: поиск + черновики + вставка в формы без submit
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'React Python CRM' \
  --query 'AI automation developer' \
  --min-score 80 \
  --limit 5 \
  --daily-limit 5

# боевой режим: нажимает HH submit в уже авторизованном browser profile
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'React Python CRM' \
  --query 'AI automation developer' \
  --min-score 85 \
  --limit 5 \
  --daily-limit 5 \
  --headless \
  --send

# shell wrapper с env-настройками; по умолчанию SEND=0
scripts/run_hh_auto_apply.sh
HH_AUTO_APPLY_SEND=1 HH_AUTO_APPLY_MIN_SCORE=85 HH_AUTO_APPLY_DAILY_LIMIT=5 scripts/run_hh_auto_apply.sh
```

`auto-apply` не берёт demo-вакансии по умолчанию, не отправляет уже отправленные заявки повторно, пишет событие `sent` и `sent_at` в CRM, а также сохраняет run log в `run_logs`.

CAPTCHA/anti-bot/429/403 считаются стоп-сигналом: система не обходит защиту и не спамит.

## HH chat follow-up

Отдельный браузерный runner проверяет `https://hh.ru/chat`, ищет реальные вопросы работодателей и отвечает короткими безопасными сообщениями из проверенного профиля Александра. Обычные ответы в HH чатах по-прежнему отправляются только с `--send` или `HH_CHAT_REPLY_SEND=1`.

Google Forms ссылки из HH чатов детектируются отдельно. Dry-run только готовит ответы. С `--send` и `--external-submit` или `HH_CHAT_EXTERNAL_SUBMIT=1` runner может заполнить и отправить только консервативно безопасные Google Forms. Он fail-closed на login/auth, CAPTCHA, non-Google URL, file upload, payments и unknown required fields.

Telegram, GigaRecruiter и другие внешние handoff не получают внешних сообщений. Вместо этого runner отправляет hhcrmbot/Telegram alert Александру: HH chat link, target handle/link и готовый copy-paste текст или ответы. Alert работает, когда настроен реальный HH Telegram chat id.

Чтобы включить alerts, запусти HH Telegram bot и отправь `/start`, либо задай `HH_TELEGRAM_CHAT_ID` реальным chat id. Placeholder `12345` игнорируется.

```bash
# dry-run: найти вопросы и сгенерировать ответы, но не отправлять
PYTHONPATH=backend python -m app.cli reply-hh-chats --limit 5 --headless

# боевой режим: отправляет ответы в авторизованном HH browser profile
PYTHONPATH=backend python -m app.cli reply-hh-chats --limit 5 --headless --send

# разрешить только безопасный submit Google Forms
PYTHONPATH=backend python -m app.cli reply-hh-chats --limit 5 --headless --send --external-submit

# shell wrapper: по умолчанию SEND=0
scripts/run_hh_chat_replies.sh
HH_CHAT_REPLY_SEND=1 HH_CHAT_EXTERNAL_SUBMIT=1 HH_CHAT_REPLY_HEADLESS=1 scripts/run_hh_chat_replies.sh

# hourly wrapper: HH_CHAT_REPLY_SEND=1, HH_CHAT_EXTERNAL_SUBMIT=1, HEADLESS=1, LIMIT=8
scripts/run_hh_chat_replies_hourly.sh

# alert-only mode без внешнего submit Google Forms
HH_CHAT_EXTERNAL_SUBMIT=0 scripts/run_hh_chat_replies_hourly.sh
```

Скрипт ведёт локальный duplicate-guard в `data/hh_chat_reply_state.json`, чтобы не отвечать повторно на один и тот же вопрос, и пишет краткий run log в CRM.

## Изолированный Telegram-агент

Отдельный бот не использует Hermes gateway и работает как самостоятельный long-polling процесс.
При запуске бот регистрирует Telegram slash-menu через `setMyCommands`, чтобы команды были видны в меню ввода.
Секреты хранятся вне git в `./.secrets/hh_telegram.env`; директория игнорируется.

```bash
# запуск демона из проекта
scripts/run_hh_telegram_agent.sh

# установка автозапуска: @reboot, watchdog каждые 5 минут, ежедневный HH-прогон 06:10 UTC
scripts/install_hh_telegram_cron.py
```

Watchdog запускает long-polling бота без стартовой рассылки (`HH_TELEGRAM_SEND_ON_START=0`), если процесс пропал. Ежедневный cron сам делает `/run`-эквивалент: no-API поиск HH, обновление CRM и отправка очереди в сохранённый чат. Если Telegram-чат ещё не зарегистрирован, ежедневный прогон пропускается до `/start`.

Команды в Telegram-боте:

- `/start` — зарегистрировать текущий chat_id и прислать текущую очередь.
- `/run` — запустить no-API поиск HH, обновить CRM и отправить свежую очередь.
- `/queue` — прислать текущие draft-вакансии выше порога с inline-кнопками.
- `/summary` — прислать краткую CRM-сводку.
- `/guide` — прислать методичку написания HH-откликов.
- `/edit ID новый текст` — заменить черновик отклика в CRM.
- `/help` — показать список команд и напоминание про безопасную отправку.

Inline-кнопки под каждой вакансией:

- `send` — открывает безопасный send-gate: бот присылает ссылку HH, черновик и кнопку `mark sent`; сам submit не нажимает.
- `edit` — показывает формат команды `/edit ID ...`.
- `reject` — отклоняет вакансию, убирает из очереди и добавляет отрицательный learning-сигнал по навыкам.
- `archive` — архивирует без обучения.

Бот отправляет вакансии, черновики и ведёт review-статусы. Реальный HH submit остаётся ручным или через отдельный browser runner с явным `--send`.

## Методичка откликов

Генератор черновиков читает `docs/cover-letter-methodology.md` или путь из `HH_COVER_LETTER_METHODOLOGY_PATH`. Главное жёсткое правило: приветствие всегда `Здравствуйте!`, без обращения к названию работодателя/ИП/ООО из карточки HH.

Пример корректного начала:

```text
Здравствуйте! Увидел вакансию «Python-разработчик AI-агентов». По описанию это как раз мой профиль: Python, LLM и Telegram.
```

## HH API

HH API требует корректный `User-Agent` / `HH-User-Agent`, желательно в формате приложения и реального контакта. `example.com` HH отклоняет как плохой User-Agent, поэтому используем реальный публичный контакт:

```bash
HH_USER_AGENT='headhunter-crm-agent/0.1 (https://portfolio.viably.dev)'
HH_CLIENT_ID=''
HH_CLIENT_SECRET=''
HH_REDIRECT_URI='http://localhost:8000/oauth/hh/callback'
HH_ACCESS_TOKEN=''
HH_REFRESH_TOKEN=''
HH_RESUME_ID=''
```

Без OAuth можно использовать no-API web-режим выше. Для просмотра своих резюме, истории откликов, сообщений и реальной отправки отклика через официальный backend нужен OAuth пользователя. Приложение регистрируется на `https://dev.hh.ru`; токен получается через `https://hh.ru/oauth/authorize` + `POST https://api.hh.ru/token`.

Реальная отправка откликов остаётся за confirmation gate: система сначала показывает вакансию и черновик, а наружу отправляет только после явного подтверждения.

## Команды

```bash
PYTHONPATH=backend python -m app.cli init-db
PYTHONPATH=backend python -m app.cli seed-demo
PYTHONPATH=backend python -m app.cli run-public-once --query 'React Python CRM' --per-query 10 --draft-threshold 80
PYTHONPATH=backend python -m app.cli export-review-queue --output ./data/review_queue.md --min-score 80
PYTHONPATH=backend python -m app.cli apply-browser-queue --min-score 80 --limit 3
PYTHONPATH=backend python -m app.cli auto-apply --query 'React Python CRM' --min-score 85 --limit 5 --daily-limit 5 --headless --send
PYTHONPATH=backend python -m app.cli reply-hh-chats --limit 5 --headless --send
PYTHONPATH=backend python -m app.cli run-once --query 'React Python CRM' --per-query 10 --draft-threshold 80
PYTHONPATH=backend python -m app.cli summary
pytest -q
```

## Данные пользователя

Реальный профиль Александра Олеговича уже сохранён в `data/profile.aleksandr.json`: 32 кейса, ключевые навыки и портфолио `https://portfolio.viably.dev`. Сырой HH-блок — `data/hh_resume_hh_blocks.md`, DOCX-версия для повторной загрузки/редактирования — `data/aleksandr_hh_experience_hh_blocks.docx`.

Шаблон для будущих правок: `data/profile.template.json`. После новых данных обновляем `profile.aleksandr.json`; backend подхватит его через `HH_PROFILE_PATH` или автоматически из `./data/profile.aleksandr.json`.

## Следующий слой

1. Live dry-run browser runner на реальном HH-аккаунте: открыть ссылки «Откликнуться», вставить черновик и руками проверить форму без `--send`.
2. После dry-run включить `auto-apply --send` с лимитами (`--min-score`, `--limit`, `--daily-limit`) и следить за `sent_at`/run logs.
3. Связать Telegram `send` с browser dry-run: готовить конкретный отклик по ID, но реальный submit оставлять за отдельным подтверждением.
4. LLM-генератор: подключить модель к `responses.py`, обязательно читая `docs/cover-letter-methodology.md` и оставив deterministic fallback.
5. OAuth HH опционально: авторизация, выбор резюме, безопасная отправка только после подтверждения.
6. Follow-up агент: напоминания через 2–4 дня после отправки.
7. Метрики конверсии: какие формулировки дают ответы/собесы/офферы.

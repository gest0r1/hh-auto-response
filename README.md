# HeadHunter CRM Agent

Production-контур для поиска работы на HH.ru: поиск вакансий, скоринг, CRM, черновики откликов, браузерная отправка, ответы в HH-чатах, Google Forms handoff и Telegram-review бот.

Главная идея: это не спам-бот. Агент собирает контекст кандидата, ищет подходящие вакансии, пишет нормальные ответы по профилю и ведет историю. Любое внешнее действие включается отдельными gate-флагами.

## Что умеет

- Искать вакансии через публичную HH-выдачу без OAuth.
- Использовать HH API, если есть OAuth-приложение и токены.
- Складывать вакансии, отклики, статусы, feedback и run logs в SQLite CRM.
- Считать fit-score под профиль кандидата, stop keywords, зарплату, формат и стек.
- Генерировать сопроводительные письма из профиля, кейсов, портфолио и текста вакансии.
- Открывать HH в Playwright-браузере, заполнять формы отклика и отправлять только при двойном подтверждении.
- Проверять HH-чаты, читать контекст диалога, отвечать на screening questions и не отвечать на quick reply chips.
- Детектировать внешние handoff: Telegram, GigaRecruiter, Google Forms, внешние анкеты.
- Заполнять только простые безопасные Google Forms через отдельный conservative runner.
- Присылать очередь и handoff alerts в отдельного Telegram-бота.
- Показывать CRM через FastAPI + React/Vite dashboard.

## Что не делает без явного разрешения

- Не обходит CAPTCHA, 403, 429, login-wall и anti-bot.
- Не отправляет отклики по умолчанию.
- Не пишет во внешние Telegram/GigaRecruiter-чаты за кандидата.
- Не отправляет Google Forms, если форма требует login, file upload, payment, неизвестное обязательное поле или non-Google URL.
- Не хранит токены, cookies, browser profile, SQLite базу и личные источники в git.

## Архитектура

```text
backend/app/
  api.py              FastAPI endpoints
  cli.py              все локальные команды
  agent.py            поиск, скоринг, черновики, learning loop
  auto_apply.py       полный цикл search -> score -> draft -> browser apply
  hh_public.py        no-API парсер публичной HH-выдачи
  hh_browser.py       Playwright runner для HH apply forms
  hh_chat.py          HH chat scanner, screening replies, external handoff detection
  google_forms.py     conservative Google Forms fill/submit runner
  responses.py        генератор сопроводительных писем
  scoring.py          deterministic vacancy scoring
  repository.py       SQLite CRM repository
  telegram_agent.py   отдельный Telegram-review бот

data/
  profile.template.json       шаблон профиля кандидата
  profile.local.json          твой локальный профиль, не коммитить
  hh_crm.sqlite3              локальная CRM, не коммитить
  hh-browser-profile/         cookies/session HH и Google, не коммитить

docs/
  cover-letter-methodology.md методичка генерации откликов
  architecture.md             техническая схема
  next-data-needed.md         какие данные нужны от кандидата

dashboard/                    React/Vite CRM dashboard
scripts/                      безопасные wrappers для cron/live режимов
tests/                        pytest coverage
```

## Быстрый старт с нуля

### 1. Склонировать и поставить зависимости

```bash
git clone git@github.com:Glour/headhunter-crm-agent.git
cd headhunter-crm-agent

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
```

Если браузерный режим не нужен, можно поставить только backend:

```bash
python -m pip install -e '.[dev]'
```

### 2. Создать локальный env и профиль

```bash
cp .env.example .env
cp data/profile.template.json data/profile.local.json
```

Открой `.env` и задай минимум:

```bash
HH_CRM_DB_PATH=./data/hh_crm.sqlite3
HH_PROFILE_PATH=./data/profile.local.json
HH_BROWSER_USER_DATA_DIR=./data/hh-browser-profile
HH_USER_AGENT=headhunter-crm-agent/0.1 (https://your-site.example)
```

`HH_USER_AGENT` должен содержать нормальный контакт: сайт, GitHub или email. HH может отклонять пустой или фейковый User-Agent.

Python-команды читают `.env` автоматически. Shell wrappers из `scripts/` тоже подхватывают `.env`, но переменные, переданные прямо в командной строке, имеют приоритет. Например `HH_CHAT_REPLY_SEND=0 scripts/run_hh_chat_replies_live_approved.sh` останется dry-run.

### 3. Заполнить профиль кандидата

Файл: `data/profile.local.json`.

Минимально нужно заполнить:

- `full_name` - имя для откликов и анкет.
- `headline` - кто ты одним предложением.
- `positioning` - 3-5 строк, чем ты полезен работодателю.
- `target_roles` - какие роли искать.
- `skills` - стек, который можно честно заявлять.
- `preferred_keywords` - что повышает score: remote, AI, backend, leadership и так далее.
- `stop_keywords` - что не подходит: office only, sales, low salary, wrong stack.
- `min_monthly_salary` - нижний порог для скоринга.
- `strengths` - 3-7 сильных доказательств.
- `cases` - реальные проекты с ролью, периодом, стеком, задачей и результатом.
- `portfolio_url`, `github_url`, `proof_pack_url` - ссылки на портфолио, GitHub, кейс-пак.
- `location`, `telegram`, `phone`, `age` - только если это реально можно отправлять работодателю.

Хороший профиль отвечает на вопросы рекрутера без выдумок. Если Vue, Kubernetes, Kafka или другой стек не был production-основой, не добавляй его как сильный навык. Лучше описать смежный опыт и готовность быстро встроиться.

### 4. Сложить источники кандидата

Создай локальные папки, они не должны попадать в git:

```bash
mkdir -p data/profile-sources data/evidence-packs data/private-notes
```

Что туда положить:

- `data/profile-sources/resume.md` - полный текст резюме.
- `data/profile-sources/hh-resume.md` - блоки из HH-резюме.
- `data/profile-sources/portfolio-links.md` - сайты, GitHub, кейсы, каналы, презентации.
- `data/profile-sources/cases.md` - все проекты: задача, роль, стек, результат, ссылки.
- `data/profile-sources/preferences.md` - формат работы, зарплата, города, стоп-компании.
- `data/evidence-packs/` - PDF, DOCX, screenshots, Yandex Disk links, proof packs.

После этого руками или отдельным скриптом перенеси выжимку в `data/profile.local.json`. Агент читает именно JSON-профиль, а raw sources нужны как долговременная база фактов.

## Первый запуск без отправки

```bash
source .venv/bin/activate
export PYTHONPATH=backend
python -m app.cli init-db
python -m app.cli run-public-once \
  --query 'Python Backend FastAPI' \
  --query 'AI Backend Engineer' \
  --query 'LLM Platform Engineer' \
  --per-query 20 \
  --draft-threshold 80

python -m app.cli export-review-queue --output ./data/review_queue.md --min-score 80
python -m app.cli summary
```

После запуска смотри `data/review_queue.md`. Там будут вакансии, score, причины, риски и черновики.

## Вход в HeadHunter через виртуальный браузер

Для реальной работы с откликами и чатами нужен persistent browser profile. Он хранит cookies локально в `data/hh-browser-profile/` и не коммитится.

Первый вход лучше делать не headless:

```bash
source .venv/bin/activate
export PYTHONPATH=backend
python -m app.cli apply-browser-queue --min-score 80 --limit 1 --user-data-dir ./data/hh-browser-profile
```

Что сделать в открывшемся браузере:

1. Войти в свой HH-аккаунт.
2. Пройти SMS/2FA, если HH попросит.
3. Убедиться, что открывается вакансия и форма отклика.
4. Закрыть браузер только после завершения команды.

Потом тот же profile можно использовать в headless cron.

## Dry-run автооткликов

Dry-run ищет вакансии, генерирует черновики и может открыть формы, но не нажимает submit.

```bash
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'Python Backend Engineer' \
  --query 'AI Backend Engineer' \
  --query 'AgentOps Engineer' \
  --per-query 20 \
  --draft-threshold 85 \
  --min-score 85 \
  --limit 5 \
  --daily-limit 5 \
  --headless
```

Shell wrapper:

```bash
scripts/run_hh_auto_apply.sh
```

## Live автоотклики

Live submit включается только двойным gate:

```bash
HH_AUTO_APPLY_SEND=1 HH_AUTO_APPLY_ALLOW_LIVE_SEND=1 \
PYTHONPATH=backend python -m app.cli auto-apply \
  --query 'Python Backend Engineer' \
  --query 'AI Backend Engineer' \
  --min-score 90 \
  --limit 3 \
  --daily-limit 5 \
  --headless \
  --send
```

Для заранее одобренного production lane есть wrapper:

```bash
HH_AUTO_APPLY_LIMIT=3 HH_AUTO_APPLY_DAILY_LIMIT=5 scripts/run_hh_auto_apply_live_approved.sh
```

После любого плохого отклика, дубля или wrong-template incident live нужно fail-close: переключить cron на dry-run, поправить генератор, прогнать тесты и только потом включать обратно.

## HH-чаты

Агент открывает `https://hh.ru/chat`, читает список диалогов, открывает кандидатов, собирает последние сообщения и отвечает только на реальные вопросы работодателя.

Dry-run:

```bash
PYTHONPATH=backend python -m app.cli reply-hh-chats \
  --limit 5 \
  --max-chats 160 \
  --headless
```

Live HH in-chat replies:

```bash
HH_CHAT_REPLY_SEND=1 HH_CHAT_REPLY_ALLOW_LIVE_SEND=1 \
PYTHONPATH=backend python -m app.cli reply-hh-chats \
  --limit 5 \
  --max-chats 160 \
  --headless \
  --send
```

Approved wrapper:

```bash
scripts/run_hh_chat_replies_live_approved.sh
```

Safety rules for chats:

- Последнее сообщение работодателя - главный вопрос.
- Контекст всего чата передается в генератор, чтобы не отвечать пустым шаблоном.
- Quick reply chips кандидата не считаются вопросом работодателя.
- Низкий fit по title, закрытый чат, duplicate, manual-required и external handoff блокируются.
- Если вопрос требует выбора скрытого варианта в UI, агент оставляет manual review.
- External Telegram/GigaRecruiter не отправляются автоматически.

## Google Forms из HH-чатов

Google Forms работает как отдельный conservative path.

Что поддерживается:

- простые текстовые поля;
- вопросы, на которые можно ответить из `profile.local.json`;
- dry-run заполнение без submit;
- submit только при live chat gate и `--external-submit`.

Что блокируется:

- Google login/auth modal;
- CAPTCHA;
- file upload;
- payment;
- неизвестные required fields;
- non-Google forms;
- формы, где нужно выбрать вариант, который runner не прочитал надежно.

Если форма просит войти в Google:

```bash
PYTHONPATH=backend python -m app.cli reply-hh-chats --limit 1 --headless
```

Если результат показывает auth-required, открой тот же browser profile не headless, войди в Google, затем повтори dry-run. Google cookies хранятся в том же `HH_BROWSER_USER_DATA_DIR`, если отдельный путь не задан.

Submit Google Forms включай только после dry-run проверки:

```bash
HH_CHAT_REPLY_SEND=1 HH_CHAT_REPLY_ALLOW_LIVE_SEND=1 HH_CHAT_EXTERNAL_SUBMIT=1 \
PYTHONPATH=backend python -m app.cli reply-hh-chats \
  --limit 1 \
  --headless \
  --send \
  --external-submit
```

## Telegram-review бот

Бот нужен для review queue, alerts и ручного управления.

1. Создай bot token через BotFather.
2. Положи token в `.secrets/hh_telegram.env`:

```bash
HH_TELEGRAM_BOT_TOKEN=<bot-token-from-botfather>
HH_TELEGRAM_CHAT_ID=
```

3. Запусти бота:

```bash
scripts/run_hh_telegram_agent.sh
```

4. Напиши `/start` боту в Telegram. Только после этого он узнает chat id.

Команды:

- `/start` - зарегистрировать chat id.
- `/run` - запустить поиск и обновить очередь.
- `/queue` - показать текущие draft-вакансии.
- `/summary` - сводка CRM.
- `/guide` - методичка откликов.
- `/edit ID новый текст` - заменить черновик.
- `/help` - помощь.

## Dashboard

Backend:

```bash
PYTHONPATH=backend HH_CRM_DB_PATH=./data/hh_crm.sqlite3 \
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd dashboard
npm install
npm run dev
```

Production build:

```bash
cd dashboard
npm run build
```

## Cron

Пример dry-run chat scan каждые 10 минут:

```cron
*/10 * * * * /path/to/headhunter-crm-agent/scripts/run_hh_chat_replies_hourly.sh >> /path/to/headhunter-crm-agent/logs/hh_chat_replies.log 2>&1
```

Пример approved live chat lane каждые 10 минут:

```cron
*/10 * * * * /path/to/headhunter-crm-agent/scripts/run_hh_chat_replies_live_approved.sh >> /path/to/headhunter-crm-agent/logs/hh_chat_replies.log 2>&1
```

Включай live cron только после dry-run inspection и тестов. Если случился плохой ответ, сразу переключай обратно на dry-run.

## Проверка перед production

```bash
source .venv/bin/activate
pytest -q
PYTHONPATH=backend python -m compileall -q backend/app
bash -n scripts/run_hh_auto_apply.sh scripts/run_hh_auto_apply_live_approved.sh scripts/run_hh_chat_replies.sh scripts/run_hh_chat_replies_hourly.sh scripts/run_hh_chat_replies_live_approved.sh
PYTHONPATH=backend python -m app.cli init-db
PYTHONPATH=backend python -m app.cli summary
```

Если есть dashboard:

```bash
cd dashboard
npm install
npm run build
```

Перед live submit дополнительно:

1. dry-run auto-apply;
2. dry-run HH chats;
3. проверить тексты черновиков;
4. проверить, что нет stale personal links, inactive channels, wrong stack claims;
5. проверить daily limit;
6. включить double gate только на маленький лимит.

## Что коммитить и что не коммитить

Коммитить можно:

- backend/app;
- tests;
- scripts;
- docs;
- README;
- `.env.example`;
- `data/profile.template.json`.

Не коммитить:

- `.env`;
- `.secrets/`;
- `data/profile.local.json`;
- `data/profile-sources/`;
- `data/evidence-packs/`;
- `data/hh_crm.sqlite3`;
- `data/hh-browser-profile/`;
- `data/hh_chat_reply_state.json`;
- logs;
- screenshots with private data;
- cookies, tokens, browser profile, raw resumes with phone/email if repo will be public.

## Troubleshooting

### Playwright is not installed

```bash
source .venv/bin/activate
python -m pip install -e '.[browser]'
python -m playwright install chromium
```

### needs_login

Открой browser runner без headless, войди в HH, потом повтори headless run.

### Агент пишет слишком общий ответ

1. Останови live cron или переключи на dry-run.
2. Найди вопрос в HH chat dry-run.
3. Добавь deterministic handler в `backend/app/hh_chat.py`.
4. Добавь regression test в `tests/test_hh_chat.py`.
5. Прогони tests и только потом включай live.

### Плохие вакансии попадают в очередь

1. Добавь stop keywords в `profile.local.json`.
2. Усиль penalties в `backend/app/scoring.py`.
3. Перескорь базу новым run-public/auto-apply dry-run.
4. Архивируй старые drafts ниже нового threshold.

### Дубли откликов

Проверь CRM по company + title, не только по HH external id. HH иногда показывает одну человеческую вакансию под разными ids.

### Google Form не заполняется

Сначала проверь dry-run. Если поля disabled и виден login modal, войди в Google в том же browser profile. Если есть unknown required fields, заполняй вручную или добавляй безопасный handler.

## Минимальный путь до своего production-агента

1. Заполнить `.env` и `profile.local.json`.
2. Сложить raw источники в `data/profile-sources/`.
3. Установить browser deps и войти в HH через persistent profile.
4. Запустить `init-db`.
5. Сделать `run-public-once` по 3-5 запросам.
6. Посмотреть `review_queue.md`, поправить profile keywords и stop keywords.
7. Прогнать `auto-apply` dry-run.
8. Прогнать `reply-hh-chats` dry-run.
9. Проверить тексты ответов на реальные screening questions.
10. Включить live только через double gates и маленькие лимиты.
11. Добавить cron.
12. Раз в день смотреть summary, queue, logs и feedback.

## Лицензия и ответственность

Код автоматизирует действия в пользовательском аккаунте HH. Используй аккуратно, соблюдай правила площадки, не обходи защиту и не отправляй массовый мусор. Хороший агент экономит время кандидата, а не портит ему репутацию.

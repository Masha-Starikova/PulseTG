# PulseTG

**PulseTG** — сервис AI-аудита Telegram-каналов с аналитикой за 30 дней, рекомендациями по росту и удобной выдачей результатов в формате Telegram Mini App.

---

## Содержание

1. [Описание проекта](#описание-проекта)
2. [Архитектура](#архитектура)
3. [Поток данных](#поток-данных)
4. [Технологический стек](#технологический-стек)
5. [Структура проекта](#структура-проекта)
6. [План разработки](#план-разработки)
7. [Локальный запуск через Docker](#локальный-запуск-через-docker)
8. [Деплой на VPS](#деплой-на-vps)
9. [Roadmap / дальнейшие улучшения](#roadmap--дальнейшие-улучшения)

---

## Описание проекта

PulseTG решает задачу быстрой и понятной диагностики Telegram-канала:

- собирает данные по постам, реакциям, просмотрам, динамике публикаций и вовлеченности;
- агрегирует их в единый аналитический профиль;
- передает метрики в AI-модуль;
- формирует рекомендации: контент, частота публикаций, точки роста, риски;
- показывает результат пользователю в Telegram Mini App.

### Ключевая ценность

- **Скорость**: аудит за минуты, а не за часы ручного анализа.
- **Системность**: единый pipeline от сбора данных до инсайтов.
- **Практичность**: вывод не только цифр, но и конкретных действий.

---

## Архитектура

Система построена как набор сервисов с четким разделением ответственности:

### 1) API-слой (`FastAPI`)

- принимает запросы на аудит;
- управляет lifecycle задач;
- отдает результаты во frontend (Mini App);
- предоставляет healthcheck и служебные эндпоинты.

### 2) Сбор данных (`Telethon`)

- подключается к Telegram API;
- получает данные канала и постов за целевой период (30 дней);
- сохраняет сырой и нормализованный слой данных.

### 3) Аналитический слой

- рассчитывает KPI: ER, частота, динамика охвата, реакций, распределение по форматам;
- готовит фичи и summary для AI.

### 4) AI-слой

- интерпретирует метрики;
- генерирует выводы и рекомендации;
- формирует структурированный отчет для Mini App.

### 5) Очереди и фоновые задачи (`Celery + Redis`)

- запускает тяжелые и длительные задачи асинхронно;
- изолирует API от долгих операций;
- обеспечивает повторные попытки и масштабируемость воркеров.

### 6) Хранилище (`PostgreSQL`)

- хранит пользователей, запросы аудита, сырые данные, агрегаты и отчеты;
- обеспечивает транзакционность и консистентность доменной модели.

### 7) Клиент (`Next.js`, Telegram Mini App)

- предоставляет UI отчета;
- показывает прогресс обработки и итоговые рекомендации;
- взаимодействует с backend API через защищенные эндпоинты.

---

## Поток данных

Пайплайн на высоком уровне:

1. Пользователь в Mini App отправляет канал на аудит.
2. `FastAPI` создает задачу и отправляет ее в `Celery`.
3. Воркер через `Telethon` забирает данные Telegram.
4. Данные проходят этап аналитической обработки.
5. AI-модуль получает аналитический контекст и генерирует выводы.
6. Итоговый отчет сохраняется в `PostgreSQL`.
7. Mini App запрашивает статус/результат и отображает отчет пользователю.

Схема:

```text
Telegram -> Collector (Telethon) -> Analytics -> AI Engine -> API -> Mini App
                      |                                |
                      v                                v
                   PostgreSQL <-> Celery/Redis <-> Task orchestration
```

---

## Технологический стек

### Backend

- `Python 3.11+`
- `FastAPI` — REST API и orchestration
- `SQLAlchemy` + `Alembic` — ORM и миграции
- `Celery` — фоновые задачи
- `Redis` — брокер очередей/кэш
- `Telethon` — интеграция с Telegram

### AI / Data

- `Pydantic` — валидация и структурирование данных
- AI provider (OpenAI/совместимый API) — генерация рекомендаций
- pandas/numpy (опционально) — дополнительные расчеты

### Frontend

- `Next.js` (App Router)
- `TypeScript`
- Telegram WebApp SDK

### Инфраструктура

- `Docker`, `Docker Compose`
- `PostgreSQL`
- `Nginx` (reverse proxy для VPS)
- `GitHub Actions` (опционально для CI/CD)

---

## Структура проекта

Ниже целевая структура (рекомендуемая для развития проекта):

```text
PulseTG/
  backend/
    app/
      api/                 # FastAPI routers
      core/                # config, security, settings
      db/                  # models, session, migrations glue
      services/            # analytics, ai, telegram collector
      tasks/               # Celery tasks
      schemas/             # Pydantic schemas
      main.py              # FastAPI entrypoint
    alembic/
    requirements.txt
    Dockerfile
  frontend/
    src/
      app/                 # Next.js routes/pages
      components/
      lib/                 # api client, telegram sdk helpers
    package.json
    Dockerfile
  infra/
    docker/
      docker-compose.yml
      .env.example
    nginx/
      pulsetg.conf
  scripts/
    bootstrap.sh
  README.md
```

---

## План разработки

### Этап 1. Базовый каркас

- инициализация backend и frontend;
- настройка Docker-окружения (`api`, `db`, `redis`, `worker`, `frontend`);
- базовая auth/идентификация пользователя Mini App.

### Этап 2. Telegram ingestion

- подключение `Telethon`;
- сбор постов/метрик за 30 дней;
- первичное сохранение данных в PostgreSQL.

### Этап 3. Аналитика

- расчет ключевых метрик;
- нормализация и формирование аналитического профиля канала;
- тесты на корректность расчетов.

### Этап 4. AI-отчет

- разработка prompt-стратегии;
- генерация рекомендаций из аналитического профиля;
- валидация структуры и качества ответов.

### Этап 5. Mini App UI

- экран ввода канала и статуса обработки;
- страница отчета (метрики + рекомендации + визуализации);
- обработка ошибок и ретраев.

### Этап 6. Production readiness

- мониторинг, логирование, алерты;
- ограничение rate-limit, retries, idempotency;
- hardening конфигурации и релиз на VPS.

---

## Локальный запуск через Docker

### 1. Предварительные требования

- Docker Engine 24+
- Docker Compose v2+
- доступ к Telegram API (`API_ID`, `API_HASH`)
- ключ AI-провайдера (`OPENAI_API_KEY` или аналог)

### 2. Подготовка `.env`

Создайте файл `.env` (или `infra/docker/.env`) на основе `.env.example`:

```env
# App
APP_ENV=local
APP_PORT=8000

# PostgreSQL
POSTGRES_DB=pulsetg
POSTGRES_USER=pulsetg
POSTGRES_PASSWORD=pulsetg
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Telegram
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=pulsetg

# AI
OPENAI_API_KEY=your_api_key
AI_MODEL=gpt-4o-mini

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 3. Запуск сервисов

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
```

### 4. Миграции БД

```bash
docker compose -f infra/docker/docker-compose.yml exec api alembic upgrade head
```

### 5. Проверка

- API: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`
- Redis/Postgres: доступны внутри docker-сети

### 6. Остановка

```bash
docker compose -f infra/docker/docker-compose.yml down
```

Для полной очистки томов:

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

---

## Деплой на VPS

Рекомендуемая схема: один VPS + Docker Compose + Nginx + SSL.

### 1) Подготовка сервера

- Ubuntu 22.04 LTS;
- установить Docker/Compose;
- открыть порты `80`, `443`, `22`;
- создать пользователя для деплоя (без работы под `root`).

### 2) Поставка приложения

- клонировать репозиторий на сервер;
- подготовить production `.env` (секреты только на сервере);
- убедиться, что `DEBUG=false`, включены безопасные cookie/headers.

### 3) Запуск сервисов

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
docker compose -f infra/docker/docker-compose.yml exec api alembic upgrade head
```

### 4) Reverse proxy и SSL

- Nginx проксирует:
  - `/` -> `frontend:3000`
  - `/api` -> `api:8000`
- сертификаты через Let's Encrypt (`certbot` или `acme.sh`).

### 5) Наблюдаемость и надежность

- включить ротацию логов;
- healthchecks для `api`, `worker`, `redis`, `db`;
- резервные копии PostgreSQL (`pg_dump` по cron);
- restart policy `unless-stopped`.

### 6) CI/CD (минимальный сценарий)

- push в `main` -> build образов -> deploy через SSH -> `docker compose pull && up -d`;
- отдельно выполнять миграции и smoke-check после релиза.

---

## Roadmap / дальнейшие улучшения

- сравнение с конкурентами в нише;
- рекомендательная система по лучшему времени публикаций;
- A/B-оценка гипотез контента;
- экспорт отчета (PDF/Notion/Google Docs);
- мультиязычная поддержка отчетов.

---

## Лицензия

Выберите и добавьте лицензию (например, `MIT` или `Apache-2.0`) перед production-использованием.

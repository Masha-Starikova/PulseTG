# PulseTG

[![tests](https://github.com/Masha-Starikova/PulseTG/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Masha-Starikova/PulseTG/actions/workflows/tests.yml)

PulseTG делает AI-аудит публичного Telegram-канала. Сервис собирает посты за 30 дней, считает метрики и формирует отчёт с рекомендациями по заданной структуре.

## Статус проекта

Это пет-проект, запускается локально через Docker Compose. В продакшене не развёрнут, реальной нагрузки не было.

Работает:

- REST API на FastAPI с валидацией запросов через Pydantic.
- Фоновый аудит в Celery с Redis: временные ошибки повторяются, постоянные сразу завершают аудит.
- Сбор постов через Telethon и расчёт ER, недельных трендов и лучшего времени публикаций.
- AI-отчёт через OpenAI с проверкой структуры Pydantic-моделью.
- PostgreSQL на async SQLAlchemy и миграции Alembic.
- Веб-интерфейс на React.

Пока нет:

- Авторизации пользователей: API открыт для всех, кто до него дотянется.
- Запуска внутри Telegram: на фронте есть заготовка для Mini App, но он работает как обычный сайт.
- Деплоя и мониторинга.

Известные ограничения перечислены в разделе [ниже](#известные-ограничения).

## Как это работает

```text
Браузер -> FastAPI -> Celery (через Redis) -> Telethon -> аналитика -> OpenAI -> PostgreSQL
   ^                                                                                |
   +------------------ опрос статуса GET /api/v1/audits/{id} -----------------------+
```

1. `POST /api/v1/audits` проверяет имя канала, создаёт запись `pending` и ставит задачу в очередь.
2. Воркер переводит аудит в `running`, забирает посты, считает метрики и запрашивает отчёт у модели.
3. Успешный аудит получает статус `completed` и отчёт. Неудачный получает `failed` и понятное `error_message`.
4. Фронт опрашивает `GET /api/v1/audits/{id}`, пока аудит не завершится.

Если AI недоступен, аудит завершается статусом `failed`. Заглушек вместо отчёта нет.

## Стек

| Часть | Технологии |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic, slowapi |
| База данных | PostgreSQL 16, SQLAlchemy (async), Alembic |
| Фоновые задачи | Celery, Redis |
| Внешние сервисы | Telethon, OpenAI API |
| Frontend | React, Vite, TypeScript, Tailwind CSS, Recharts |
| Инфраструктура | Docker Compose, Nginx (раздача фронта), GitHub Actions |

## Структура проекта

```text
backend/
  ai/          клиент OpenAI, проверка структуры отчёта
  analytics/   расчёт метрик
  api/         эндпоинты
  core/        настройки, база, Redis, Celery, rate limit
  migrations/  миграции Alembic
  models/      ORM-модели
  schemas/     Pydantic-схемы API
  services/    сценарий аудита и задача Celery
  telegram/    сбор постов через Telethon
  tests/       тесты pytest
frontend/      интерфейс на React + Vite
scripts/       создание session-файла Telegram
```

## Запуск

Нужны Docker с Compose, ключи Telegram API с https://my.telegram.org и ключ OpenAI.

```bash
cp .env.example .env
# заполните значения в .env по комментариям
PYTHONPATH=. python scripts/init_session.py   # один раз, нужен вход в Telegram
docker compose up --build -d
```

`scripts/init_session.py` запускается на вашей машине, а не в контейнере. Ему нужны зависимости из `backend/requirements.txt`. Он создаёт файл `backend/telegram/<TELEGRAM_SESSION_NAME>.session`, этот файл даёт доступ к вашему аккаунту Telegram и в git не попадает.

Миграции применяются автоматически отдельным сервисом `migrate` при запуске.

| Адрес | Что там |
| --- | --- |
| http://localhost:3000 | Веб-интерфейс |
| http://localhost:8000/docs | Документация API |
| http://localhost:8000/api/v1/health | Проверка состояния |

## Тесты

Тестам нужны настоящие PostgreSQL и Redis: модели используют типы UUID и JSONB, поэтому SQLite не подходит. Контейнеры из `docker-compose.test.yml` работают на отдельных портах и хранят данные в памяти, dev-база не затрагивается.

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements-dev.txt

docker compose -f docker-compose.test.yml up -d --wait
pytest --cov --cov-report=term-missing
docker compose -f docker-compose.test.yml down
```

Запускайте команды из корня репозитория.

Что важно знать:

- Схема базы создаётся настоящими миграциями Alembic, отдельный тест проверяет их совпадение с моделями.
- Исходящие соединения заблокированы через pytest-socket, разрешён только localhost. OpenAI и Telegram заменены моками.
- Тесты не запустятся на базе, имя которой не заканчивается на `_test`.

Те же тесты запускаются в GitHub Actions на каждый push и pull request.

## Известные ограничения

- Rate limit хранится в памяти процесса и считается по адресу соединения. За Nginx все пользователи выглядят как один адрес. При нескольких процессах API у каждого свой счётчик.
- Если воркер упадёт посреди аудита, запись останется в статусе `running`. Задача, потерянная после постановки в очередь, оставит запись в `pending`.
- Время публикаций считается в UTC, а не в часовом поясе аудитории канала.
- Защита от инъекций в промпт снижает риск, но не исключает его. Пост может повлиять на текст отчёта, но код не выполнит ничего из ответа модели.
- Повтор задачи запускает аудит заново, включая сбор постов из Telegram.

## Лицензия

Лицензия пока не выбрана.

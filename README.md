# Jira Throughput Forecaster

Сервис прогнозирования пропускной способности команды на основе данных из Jira.

Использует **Monte Carlo симуляцию** для предсказания количества спринтов/дней, необходимых для завершения заданного объёма работы.

## Возможности

- **Интеграция с Jira** — автоматический импорт спринтов, задач, отчётов
- **Velocity-аналитика** — средняя скорость, тренды, completion rate
- **Cycle Time** — медиана, 85/95 перцентили времени выполнения задач
- **Throughput** — ежедневная и спринтовая пропускная способность
- **Monte Carlo прогнозирование** — два режима:
  - **Sprint Velocity** — по story points (сколько спринтов нужно для N SP?)
  - **Daily Throughput** — по количеству задач (сколько спринтов нужно для N задач?)
- **REST API** — полный набор эндпоинтов для интеграции
- **Дашборд** — веб-интерфейс с графиками и прогнозами

## Быстрый старт

```bash
# Установка зависимостей
python3 -m venv djenv
source djenv/bin/activate
pip install -r requirements.txt

# Инициализация БД
python manage.py migrate

# Генерация демо-данных (без подключения к Jira)
python manage.py generate_demo_data

# Запуск сервера
python manage.py runserver
```

Откройте http://localhost:8000 для дашборда.

## Подключение к Jira

Установите переменные окружения:

```bash
export JIRA_BASE_URL="https://your-org.atlassian.net"
export JIRA_USER_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-jira-api-token"
```

Создайте команду через API или Django Admin:

```bash
# Через API
curl -X POST http://localhost:8000/api/teams/ \
  -H "Content-Type: application/json" \
  -d '{"name": "My Team", "jira_board_id": 123, "jira_project_key": "PROJ"}'

# Запуск синхронизации
python manage.py sync_jira
```

## API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/teams/` | Список команд |
| GET | `/api/teams/{id}/dashboard/` | Дашборд команды (все метрики) |
| GET | `/api/teams/{id}/velocity/` | Velocity-статистика |
| GET | `/api/teams/{id}/cycle_time/` | Cycle time статистика |
| GET | `/api/teams/{id}/throughput/` | Throughput статистика |
| POST | `/api/teams/{id}/sync/` | Синхронизация данных из Jira |
| POST | `/api/teams/{id}/forecast/throughput/` | Monte Carlo прогноз (по задачам) |
| POST | `/api/teams/{id}/forecast/sprint/` | Monte Carlo прогноз (по SP) |
| GET | `/api/sprints/` | Список спринтов |
| GET | `/api/issues/` | Список задач |
| GET | `/api/forecasts/` | Сохранённые прогнозы |

### Пример прогноза

```bash
curl -X POST http://localhost:8000/api/teams/1/forecast/throughput/ \
  -H "Content-Type: application/json" \
  -d '{
    "target_items": 30,
    "sprint_length_days": 14,
    "history_days": 90,
    "simulations": 10000
  }'
```

Ответ содержит перцентили — вероятностные оценки:

| Перцентиль | Значение | Интерпретация |
|-----------|----------|---------------|
| **P50** | 3.0 спринтов | 50% вероятность завершить за 3 спринта |
| **P70** | 3.5 спринтов | 70% вероятность |
| **P85** | 4.0 спринтов | 85% — рекомендуемое для планирования |
| **P95** | 5.0 спринтов | 95% — консервативная оценка |

## Как работает прогнозирование

1. Берутся исторические данные о пропускной способности команды
2. Запускается Monte Carlo симуляция (10 000 итераций по умолчанию)
3. В каждой итерации случайным образом выбираются исторические значения throughput
4. Подсчитывается, сколько спринтов потребуется для завершения целевого количества задач
5. Из распределения результатов вычисляются перцентили

## Стек технологий

- Python 3.12+
- Django + Django REST Framework
- NumPy + SciPy (статистика и симуляции)
- Chart.js (визуализация на фронтенде)
- SQLite (по умолчанию, легко заменяется на PostgreSQL)

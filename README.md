# Weekly Workload FastAPI Service

Simple FastAPI service that loads employee surnames and weekly workload from an Excel file.

## Rules

- Weekly workload is measured in **days per week**.
- Allowed range: **0 to 5**.
- Allowed step: **0.5 day**.

## Expected Excel format

Use the first row as headers and include:

- surname column: one of `surname`, `last_name`, `lastname`, `family_name`, `familyname`, `Фамилия`
- load column: one of `weekly_load`, `load_per_week`, `week_load`, `load_days`, `weekly_load_days`, `Загрузка`, `Нагрузка`, `Загрузка в неделю`

Example:

| surname | weekly_load |
|---------|-------------|
| Ivanov  | 5           |
| Petrov  | 3.5         |
| Sidorov | 0.5         |

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload
```

Service endpoints:

- `GET /health`
- `POST /api/v1/workloads/upload` (multipart file upload)
- `GET /api/v1/workloads`
- `GET /api/v1/workloads/summary`
- `GET /api/v1/workloads/{surname}`

OpenAPI docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Upload example

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/workloads/upload" \
  -F "file=@employees.xlsx"
```

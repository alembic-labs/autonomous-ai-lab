FROM python:3.11-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY alembic-labs-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic-labs-backend/alembic_labs ./alembic_labs

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "alembic_labs.main:app", "--host", "0.0.0.0", "--port", "8000"]

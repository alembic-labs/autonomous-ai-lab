FROM python:3.11-slim
WORKDIR /app

# WeasyPrint needs Pango / Cairo / GdkPixbuf / harfbuzz at runtime to render
# the /report.pdf download endpoint. The dev headers (-dev) are only required
# at install time but kept for predictability in case future deps need them.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY alembic-labs-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic-labs-backend/alembic_labs ./alembic_labs

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "alembic_labs.main:app", "--host", "0.0.0.0", "--port", "8000"]

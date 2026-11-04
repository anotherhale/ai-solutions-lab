FROM python:3.12-slim

WORKDIR /srv/app

COPY services/wasatch-api /srv/app
COPY data/fixtures/valid /srv/data/fixtures/valid

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

ENV WASATCH_FIXTURES_DIR=/srv/data/fixtures/valid
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && wasatch-api seed && uvicorn wasatch_api.main:app --host 0.0.0.0 --port 8000"]

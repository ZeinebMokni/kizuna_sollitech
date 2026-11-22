FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev
COPY qatra_ai ./qatra_ai
COPY examples ./examples

EXPOSE 8100
CMD ["uv", "run", "uvicorn", "qatra_ai.service.app:app", "--host", "0.0.0.0", "--port", "8100"]

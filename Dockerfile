FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e ".[standard]" 2>/dev/null || pip install --no-cache-dir .

COPY src ./src
COPY tests ./tests

EXPOSE 8000

CMD ["python", "-m", "skyq_mcp"]

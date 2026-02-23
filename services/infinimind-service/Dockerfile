# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

# Keep Python deterministic and quiet inside containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies directly from the project metadata.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Docker-first persistent state directory.
RUN mkdir -p /var/lib/infinimind
VOLUME ["/var/lib/infinimind"]

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

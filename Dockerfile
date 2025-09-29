# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim

WORKDIR /app

# Копируем установленные зависимости из builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем код приложения
COPY . /app

# Добавляем non-root user для безопасности
RUN useradd -m appuser
USER appuser

# Открываем порт
EXPOSE 8000

# Команда запуска с переменными окружения (для БД)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
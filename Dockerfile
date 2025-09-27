# Базовый образ с Python
FROM python:3.12-slim

# Установка рабочей директории
WORKDIR /app

# Копирование файлов проекта в контейнер
COPY . /app

# Установка зависимостей
RUN pip install --no-cache-dir fastapi uvicorn pydantic python-jose cryptography passlib[bcrypt]

# Открытие порта
EXPOSE 8000

# Команда для запуска приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
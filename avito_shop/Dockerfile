# Используем официальный образ Python (на примере версии 3.9)
FROM python:3.9-slim

WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код проекта
COPY . .

# Запускаем приложение через Uvicorn на порту 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

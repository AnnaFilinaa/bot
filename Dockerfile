# Используем официальный минимальный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для PostgreSQL клиента
RUN apt-get update && apt-get install -y postgresql-client && apt-get clean

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем права на скрипт ожидания
RUN chmod +x /app/wait-for-postgres.sh

# Указываем точку входа
ENTRYPOINT ["/app/wait-for-postgres.sh", "postgres-db", "python", "main.py"]

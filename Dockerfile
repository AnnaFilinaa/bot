# Используем официальный минимальный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем права на скрипт ожидания
RUN chmod +x /app/wait-for-postgres.sh

# Указываем точку входа
ENTRYPOINT ["/app/wait-for-postgres.sh", "postgres-db", "python", "main.py"]

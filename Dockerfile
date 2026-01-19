FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для компиляции некоторых пакетов
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN pip install --upgrade pip setuptools wheel

# Копируем и ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Команда для старта бота
CMD ["python", "-m", "bot.main"]

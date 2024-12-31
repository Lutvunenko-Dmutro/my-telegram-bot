# Використання базового образу Python
FROM python:3.12-slim

# Встановлення залежностей
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копіювання коду
COPY . /app
WORKDIR /app

# Встановлення ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Запуск бота
CMD ["python", "telegram_bot.py"]
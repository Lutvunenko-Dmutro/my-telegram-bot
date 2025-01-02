import os
import logging
import asyncio  # Додано імпорт asyncio
import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import subprocess
from dotenv import load_dotenv
from telegram.error import Conflict

# Завантаження змінних середовища з файлу .env
load_dotenv()

# Встановлення логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Підключення до бази даних PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )
    return conn

# Функція старту бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привіт! Надішліть мені посилання на YouTube відео, і я завантажу його для вас.')

# Функція для зупинки бота
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Зупинка бота...')
    await context.application.stop()
    await update.message.reply_text('Бот зупинено.')

# Функція для завантаження відео з YouTube
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    original_video_path = ''
    resized_video_path = ''
    if "youtube.com" in url or "youtu.be" in url:
        try:
            logger.info(f"Починаємо завантаження відео з URL: {url}")
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',  # Завантажити найкраще доступне відео та аудіо
                'outtmpl': 'videos/original_video.%(ext)s',
                'noplaylist': True  # Завантажити лише одне відео
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = await asyncio.get_event_loop().run_in_executor(None, ydl.extract_info, url)
                video_extension = info_dict['ext']
                original_video_path = f'videos/original_video.{video_extension}'
            logger.info("Завершено завантаження відео")

            # Зменшуємо розмір відео до 50 МБ
            resized_video_path = 'videos/resized_video.mp4'
            await resize_video(original_video_path, resized_video_path)

            # Перевірка розміру файлу
            file_size_mb = os.path.getsize(resized_video_path) / (1024 * 1024)
            if file_size_mb > 50:
                await update.message.reply_text(f'Файл занадто великий для відправки через Telegram. Максимальний розмір: 50 МБ. Поточний розмір: {file_size_mb:.2f} МБ.')
            else:
                # Відправка відео через Telegram
                logger.info("Починаємо відправку відео через Telegram")
                with open(resized_video_path, 'rb') as video:
                    await update.message.reply_video(video)
                logger.info("Відео успішно відправлено")
                await update.message.reply_text('Відео успішно завантажено та відправлено!')

        except Exception as e:
            logger.error(f"Помилка при завантаженні відео: {e}")
            await update.message.reply_text('Сталася помилка при завантаженні відео. Переконайтеся, що ви надіслали правильне посилання.')
        finally:
            # Очищення тимчасових файлів
            try:
                if original_video_path and os.path.exists(original_video_path):
                    os.remove(original_video_path)
                if resized_video_path and os.path.exists(resized_video_path):
                    os.remove(resized_video_path)
            except PermissionError as e:
                logger.error(f"Помилка при видаленні файлу: {e}")
    else:
        await update.message.reply_text('Будь ласка, надішліть дійсне посилання на YouTube.')

# Асинхронна функція для зменшення розміру відео
async def resize_video(input_path, output_path):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, actual_resize_video, input_path, output_path)

# Синхронна функція для зменшення розміру відео
def actual_resize_video(input_path, output_path):
    logger.info(f"Починаємо зменшення розміру відео: {input_path}")
    command = [
        'ffmpeg',
        '-i', input_path,
        '-vf', 'scale=-2:720',  # Зменшуємо розмір відео до 720p
        '-c:v', 'libx264',  # Використовуємо кодек H.264 для кращої сумісності
        '-preset', 'slow',  # Використовуємо повільніший пресет для кращого стиснення
        '-crf', '28',  # Встановлюємо фактор якості для VBR
        '-c:a', 'aac',  # Використовуємо AAC кодек для аудіо
        '-b:a', '128k',
        '-movflags', '+faststart',  # Додаємо параметр для швидшого старту відтворення
        '-y', output_path
    ]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        logger.error(f"Помилка при кодуванні відео: {process.stderr.decode()}")
    else:
        logger.info(f"Завершено зменшення розміру відео: {output_path}")

# Обробник помилок
async def error_handler(update, context):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        raise context.error
    except Conflict:
        logger.error("Конфлікт: бот вже запущений на іншому сервері або процесі")

# Визначення функції main
def main() -> None:
    # Встановлення токену Telegram бота
    token = os.getenv('TOKEN')

    application = ApplicationBuilder().token(token).read_timeout(60).write_timeout(60).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))  # Додаємо команду для зупинки бота
    application.add_handler(MessageHandler(filters.Regex(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'), download_video))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
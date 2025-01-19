import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession
import asyncio

# Подключение к переменным окружения
API_TOKEN = os.getenv('API_TOKEN')
SUPPORT_GROUP_ID = os.getenv('SUPPORT_GROUP_ID')

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')

DB_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем сессию для бота
session = AiohttpSession()

# Создаем бота
bot = Bot(token=API_TOKEN, session=session)
dp = Dispatcher()

# Словари для хранения данных
user_message_tasks = {}
topic_messages = {}

def ensure_database_exists():
    """Проверяет и создает базу данных, если она отсутствует."""
    conn = psycopg2.connect(
        dbname="postgres",  # Подключение к системной базе данных
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Проверяем, существует ли база данных
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    if not cursor.fetchone():
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        logger.info(f"Database {DB_NAME} created.")
    else:
        logger.info(f"Database {DB_NAME} already exists.")

    cursor.close()
    conn.close()

def init_db():
    """Инициализирует таблицы в базе данных PostgreSQL."""
    ensure_database_exists()  # Убедиться, что база существует
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_topics (
            user_id TEXT PRIMARY KEY,
            topic_id INTEGER UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def get_topic_id(user_id):
    """Получает topic_id для пользователя из базы данных."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT topic_id FROM user_topics WHERE user_id = %s', (str(user_id),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_id(topic_id):
    """Получает user_id для темы из базы данных."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM user_topics WHERE topic_id = %s', (topic_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_topic_id(user_id, topic_id):
    """Сохраняет соответствие user_id и topic_id в базу данных."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_topics (user_id, topic_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET topic_id = EXCLUDED.topic_id
    ''', (str(user_id), topic_id))
    conn.commit()
    conn.close()

@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer("Привет! Напиши свой вопрос, и мы ответим на него как можно скорее.")

@dp.message(lambda message: message.chat.type == "private")
async def handle_user_message(message: Message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    user_username = message.from_user.username or ''
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"

    topic_id = get_topic_id(user_id)

    try:
        if not topic_id:
            raise ValueError("Тема отсутствует")

        # Пробуем отправить сообщение в существующую тему
        sent_message = await bot.copy_message(
            chat_id=int(SUPPORT_GROUP_ID),
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )

    except (Exception, ValueError):
        logger.warning(f"Тема для пользователя {user_id} не найдена. Создаем новую тему.")

        # Создаем новую тему
        if user_username:
            topic_name = f"{user_name} | @{user_username} | {user_id}"
        else:
            topic_name = f"{user_name} | {user_id}"

        topic = await bot.create_forum_topic(chat_id=int(SUPPORT_GROUP_ID), name=topic_name)
        topic_id = topic.message_thread_id

        set_topic_id(user_id, topic_id)

        text = f"Обращение от {user_link}"
        await bot.send_message(
            chat_id=int(SUPPORT_GROUP_ID),
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML"
        )

        sent_message = await bot.copy_message(
            chat_id=int(SUPPORT_GROUP_ID),
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )

    if topic_id not in topic_messages:
        topic_messages[topic_id] = set()
    topic_messages[topic_id].add(sent_message.message_id)

    if user_id in user_message_tasks:
        user_message_tasks[user_id].cancel()

    async def send_delayed_message():
        try:
            await asyncio.sleep(30)
            await message.answer("Ваше обращение отправлено в техническую поддержку.")
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(send_delayed_message())
    user_message_tasks[user_id] = task

# Обработчик ответов от техподдержки
@dp.message(lambda message: str(message.chat.id) == SUPPORT_GROUP_ID)
async def handle_support_reply(message: Message):
    if message.message_thread_id:
        topic_id = message.message_thread_id
        user_id = get_user_id(topic_id)

        if user_id:
            if message.reply_to_message and message.reply_to_message.message_id in topic_messages.get(topic_id, set()):
                await bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                logger.info(f"Ответ поддержки отправлен пользователю {user_id}.")

                if user_id in user_message_tasks:
                    user_message_tasks[user_id].cancel()
                    del user_message_tasks[user_id]
            else:
                logger.info("Сообщение не является ответом на сообщение клиента. Не отправляем пользователю.")
        else:
            logger.error("Не найден пользователь для данной темы.")
    else:
        logger.error("Сообщение не содержит message_thread_id.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

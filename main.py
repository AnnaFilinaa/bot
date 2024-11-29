import os
import logging
import psycopg2
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.client.session.aiohttp import AiohttpSession
import asyncio

API_TOKEN = "7306703210:AAGaafa05SGa9loovceBZXor1TZWfd-3s4Q"
SUPPORT_GROUP_ID = "-1002364803574"

DB_URL = 'postgresql://postgres:TYBBvBXpDKGBfXwLJCJhZUzcOcKobtYw@postgres.railway.internal:5432/railway'

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем сессию для бота
session = AiohttpSession()

# Создаем бота
bot = Bot(token=API_TOKEN, session=session)
dp = Dispatcher()

# Словарь для хранения задач по пользователям
user_message_tasks = {}

def init_db():
    """Инициализирует базу данных PostgreSQL."""
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
    """Получает user_id по topic_id из базы данных."""
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

# Обработчик команды /start
@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer("Привет! Напиши свой вопрос, и мы ответим на него как можно скорее.")

# Обработчик сообщений от пользователей
@dp.message(lambda message: message.chat.type == "private")
async def handle_user_message(message: Message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    user_username = message.from_user.username or ''
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    topic_id = get_topic_id(user_id)

    if not topic_id:
        # Формируем название темы
        if user_username:
            topic_name = f"{user_name} | @{user_username} | {user_id}"
        else:
            topic_name = f"{user_name} | {user_id}"

        # Создание новой темы
        topic = await bot.create_forum_topic(chat_id=int(SUPPORT_GROUP_ID), name=topic_name)
        topic_id = topic.message_thread_id
        set_topic_id(user_id, topic_id)

        # Отправляем первое сообщение в тему
        text = f"Обращение от {user_link}"
        await bot.send_message(
            chat_id=int(SUPPORT_GROUP_ID),
            message_thread_id=topic_id,
            text=text,
            parse_mode="HTML"
        )

    await bot.copy_message(
        chat_id=int(SUPPORT_GROUP_ID),
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        message_thread_id=topic_id
    )

    # Обработка отложенного сообщения пользователю
    if user_id in user_message_tasks:
        # Отменяем предыдущую задачу
        user_message_tasks[user_id].cancel()

    # Создаем новую задачу
    async def send_delayed_message():
        try:
            await asyncio.sleep(30)  # Ожидаем 30 секунд
            await message.answer("Ваше обращение отправлено в техническую поддержку.")
        except asyncio.CancelledError:
            # Задача была отменена, ничего не делаем
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
            if message.reply_to_message:
                await bot.copy_message(
                    chat_id=int(user_id),
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                logger.info(f"Ответ поддержки отправлен пользователю {user_id}.")

                # Отменяем отложенное сообщение, если оно еще не отправлено
                if user_id in user_message_tasks:
                    user_message_tasks[user_id].cancel()
                    del user_message_tasks[user_id]
            else:
                # Не пересылаем сообщение, если оно не является ответом
                logger.info("Сообщение не является ответом, не отправляем пользователю.")
        else:
            logger.error("Не найден пользователь для данной темы.")
    else:
        logger.error("Сообщение не содержит message_thread_id.")


async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

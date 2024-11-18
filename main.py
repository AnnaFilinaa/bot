import os
import logging
import psycopg2
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.client.default import DefaultBotProperties
import asyncio

API_TOKEN = "7306703210:AAGaafa05SGa9loovceBZXor1TZWfd-3s4Q"
SUPPORT_GROUP_ID = "-1002364803574"

DB_URL = 'postgresql://postgres:TYBBvBXpDKGBfXwLJCJhZUzcOcKobtYw@postgres.railway.internal:5432/railway'

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def init_db():
    """Инициализирует базу данных PostgreSQL."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_topics (
            user_id TEXT PRIMARY KEY,
            topic_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_topic_id(user_id):
    """Получает topic_id для пользователя из базы данных."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('SELECT topic_id FROM user_topics WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_topic_id(user_id, topic_id):
    """Сохраняет соответствие user_id и topic_id в базу данных."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO user_topics (user_id, topic_id) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET topic_id = EXCLUDED.topic_id', (user_id, topic_id))
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
    topic_id = get_topic_id(user_id)

    if not topic_id:
        # Создание новой темы
        topic = await bot.create_forum_topic(chat_id=int(SUPPORT_GROUP_ID), name=user_name)
        topic_id = topic.message_thread_id
        set_topic_id(user_id, topic_id)

        await bot.send_message(chat_id=int(SUPPORT_GROUP_ID), message_thread_id=topic_id, text=f"Обращение от {user_name}")

    await bot.copy_message(chat_id=int(SUPPORT_GROUP_ID), from_chat_id=message.chat.id, message_id=message.message_id, message_thread_id=topic_id)
    await message.answer("Ваше сообщение отправлено в техническую поддержку.")

# Обработчик ответов от техподдержки
@dp.message(lambda message: str(message.chat.id) == SUPPORT_GROUP_ID)
async def handle_support_reply(message: Message):
    if message.reply_to_message and message.reply_to_message.message_thread_id:
        topic_id = message.reply_to_message.message_thread_id
        user_id = get_topic_id(topic_id)

        if user_id:
            await bot.send_message(chat_id=int(user_id), text=message.text)
            logger.info(f"Ответ поддержки отправлен пользователю {user_id}.")
        else:
            logger.error("Не найден пользователь для данной темы")
    else:
        logger.error("Сообщение не содержит reply_to_message с message_thread_id")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

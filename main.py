import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType
import asyncio

# # Получаем переменные окружения
# API_TOKEN = os.getenv('API_TOKEN')
# # SUPPORT_GROUP_ID = int(os.getenv('SUPPORT_GROUP_ID'))
# SUPPORT_GROUP_ID = os.getenv('SUPPORT_GROUP_ID')
#
# if API_TOKEN is None:
#     raise ValueError("Не задан API_TOKEN")
# if SUPPORT_GROUP_ID is None:
#     raise ValueError("Не задан SUPPORT_GROUP_ID")

API_TOKEN = "7306703210:AAGaafa05SGa9loovceBZXor1TZWfd-3s4Q"
SUPPORT_GROUP_ID ="-1002364803574"


# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем бота с указанием DefaultBotProperties для HTML-разметки
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Словарь для хранения соответствия пользователей и ID тем
user_topics = {}

async def get_existing_topics():
    """Загружает существующие темы из истории сообщений группы поддержки"""
    existing_topics = {}
    try:
        offset = 0
        limit = 100
        while True:
            messages = await bot.get_chat_history(chat_id=SUPPORT_GROUP_ID, offset=offset, limit=limit)
            if not messages:
                break
            for message in messages:
                # Проверяем наличие созданной темы
                if message.forum_topic_created:
                    topic_id = message.message_thread_id
                    topic_name = message.forum_topic_created.name
                    user_id = extract_user_id_from_topic_name(topic_name)
                    if user_id:
                        existing_topics[user_id] = topic_id
            if len(messages) < limit:
                break
            offset += limit
        return existing_topics
    except Exception as e:
        logger.error(f"Ошибка при получении существующих тем: {e}")
        return existing_topics

def extract_user_id_from_topic_name(topic_name):
    """Извлекает user_id из названия темы (предполагая, что user_id включен в название темы)"""
    parts = topic_name.split('|')
    if len(parts) >= 3:
        user_id_str = parts[2].strip()
        if user_id_str.isdigit():
            return int(user_id_str)
    return None

# Обработчик команды /start
async def cmd_start(message: Message):
    await message.answer("Привет! Напиши свой вопрос, и мы ответим на него как можно скорее.")

dp.message.register(cmd_start, Command(commands=["start"]))

# Обработчик сообщений от пользователей
async def handle_user_message(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    user_username = message.from_user.username or ''
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"

    # Формируем название темы, включая user_id
    topic_name = f"{user_name} | @{user_username} | {user_id}" if user_username else f"{user_name} | {user_id}"

    # Проверяем, есть ли уже тема для этого пользователя
    topic_id = user_topics.get(user_id)
    if not topic_id:
        # Если темы нет, создаём новую
        try:
            # Создаем новую тему, если не нашли
            topic = await bot.create_forum_topic(chat_id=SUPPORT_GROUP_ID, name=topic_name)
            topic_id = topic.message_thread_id
            user_topics[user_id] = topic_id

            await bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
                text=f"{user_link} создал новую тему для связи.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при создании темы: {e}")
            await message.answer("Произошла ошибка при обращении в поддержку.")
            return

    # Пересылаем сообщение пользователя в соответствующую тему
    try:
        await bot.copy_message(
            chat_id=SUPPORT_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        await message.answer("Ваше сообщение отправлено в техническую поддержку.")
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения: {e}")
        await message.answer("Не удалось отправить сообщение в поддержку.")

dp.message.register(handle_user_message, lambda message: message.chat.type == ChatType.PRIVATE)

# Обработчик ответов от техподдержки
async def handle_support_reply(message: Message):
    if message.from_user.is_bot:
        return

    if message.message_thread_id:
        user_id = None
        for uid, topic_id in user_topics.items():
            if topic_id == message.message_thread_id:
                user_id = uid
                break

        if user_id:
            try:
                if message.content_type == ContentType.TEXT:
                    await bot.send_message(chat_id=user_id, text=message.text)
                else:
                    await bot.send_message(chat_id=user_id, text="Получено сообщение от поддержки.")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения клиенту: {e}")
        else:
            logger.error("Не найден пользователь для данной темы")

dp.message.register(
    handle_support_reply,
    lambda message: message.chat.id == SUPPORT_GROUP_ID
)

async def main():
    global user_topics
    user_topics = await get_existing_topics()

    try:
        chat = await bot.get_chat(SUPPORT_GROUP_ID)
        logger.info(f"Бот успешно получил доступ к группе: {chat.title}")
    except Exception as e:
        logger.error(f"Ошибка доступа к группе: {e}")
        return

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

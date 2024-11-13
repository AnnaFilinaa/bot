import os
import logging
import json
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ContentType
from aiogram.client.session.aiohttp import AiohttpSession
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

# Путь к файлу для сохранения данных
DATA_FILE = 'user_topics.json'

def save_user_topics():
    """Сохраняет словарь user_topics в JSON-файл."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_topics, f)
        logger.info("Данные user_topics успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении user_topics: {e}")

def load_user_topics():
    """Загружает словарь user_topics из JSON-файла."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info("Данные user_topics успешно загружены.")
            return data
        except Exception as e:
            logger.error(f"Ошибка при загрузке user_topics: {e}")
            return {}
    else:
        logger.info("Файл user_topics.json не найден. Создается новый.")
        return {}

# Обработчик команды /start
async def cmd_start(message: Message):
    await message.answer("Привет! Напиши свой вопрос, и мы ответим на него как можно скорее.")

dp.message.register(cmd_start, Command(commands=["start"]))

# Обработчик сообщений от пользователей
async def handle_user_message(message: Message):
    user_id = str(message.from_user.id)  # Приводим к строке для JSON
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
            # Создаем новую тему
            topic = await bot.create_forum_topic(
                chat_id=int(SUPPORT_GROUP_ID),
                name=topic_name,
                icon_color=0xF4A460  # Пример цвета, можно изменить
            )
            topic_id = topic.message_thread_id
            user_topics[user_id] = topic_id
            save_user_topics()  # Сохраняем обновленный словарь

            await bot.send_message(
                chat_id=int(SUPPORT_GROUP_ID),
                message_thread_id=topic_id,
                text=f"Чат с {user_link}",
                parse_mode="HTML"
            )
            logger.info(f"Создана новая тема для пользователя {user_id} с ID {topic_id}.")
        except Exception as e:
            logger.error(f"Ошибка при создании темы: {e}")
            await message.answer("Произошла ошибка при обращении в поддержку.")
            return

    # Пересылаем сообщение пользователя в соответствующую тему
    try:
        await bot.copy_message(
            chat_id=int(SUPPORT_GROUP_ID),
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        await message.answer("Ваше сообщение отправлено в техническую поддержку.")
        logger.info(f"Сообщение от пользователя {user_id} переслано в тему {topic_id}.")
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
                    await bot.send_message(chat_id=int(user_id), text=message.text)
                else:
                    await bot.send_message(chat_id=int(user_id), text="Получено сообщение от поддержки.")
                logger.info(f"Ответ поддержки отправлен пользователю {user_id}.")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения клиенту: {e}")
        else:
            logger.error("Не найден пользователь для данной темы")
    else:
        logger.error("Сообщение не содержит message_thread_id")

dp.message.register(
    handle_support_reply,
    lambda message: str(message.chat.id) == SUPPORT_GROUP_ID
)

async def main():
    global user_topics
    user_topics = load_user_topics()

    try:
        chat = await bot.get_chat(int(SUPPORT_GROUP_ID))
        logger.info(f"Бот успешно получил доступ к группе: {chat.title}")
    except Exception as e:
        logger.error(f"Ошибка доступа к группе: {e}")
        return

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

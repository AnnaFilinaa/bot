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

# Функция для извлечения user_id из названия темы
def extract_user_id_from_topic_name(topic_name):
    parts = topic_name.split('|')
    if len(parts) >= 3:
        user_id_str = parts[2].strip()
        if user_id_str.isdigit():
            return int(user_id_str)
    return None

# Функция для получения существующих тем из истории сообщений
async def get_existing_topics():
    existing_topics = {}
    try:
        offset = 0
        limit = 100
        while True:
            messages = await bot.get_chat_history(chat_id=SUPPORT_GROUP_ID, offset=offset, limit=limit)
            if not messages:
                break
            for message in messages:
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

# Обработчик команды /start
async def cmd_start(message: Message):
    await message.answer("""Привет!
Напиши свой вопрос, и мы ответим на него как можно скорее.

Оформить заказ: www.heartz.immo""")


# Регистрация обработчика команды /start
dp.message.register(cmd_start, Command(commands=["start"]))


# Обработчик сообщений от пользователей
async def handle_user_message(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    user_username = message.from_user.username or ''
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"

    # Формируем название темы, включая user_id
    if user_username:
        topic_name = f"{user_name} | @{user_username} | {user_id}"
    else:
        topic_name = f"{user_name} | {user_id}"

    # Проверяем, есть ли уже тема для этого пользователя
    topic_id = user_topics.get(user_id)
    if not topic_id:
        # Если темы нет, создаём новую
        try:
            # Создаем новую тему в группе поддержки
            topic = await bot.create_forum_topic(
                chat_id=SUPPORT_GROUP_ID,
                name=topic_name
            )
            topic_id = topic.message_thread_id
            user_topics[user_id] = topic_id  # Добавляем новую тему в соответствие

            # Отправляем ссылку на профиль пользователя в новую тему поддержки
            if user_username:
                text = f"{user_name} | @{user_username}:"
            else:
                text = f"{user_link}:"
            await bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при создании темы: {e}")
            await message.answer("Произошла ошибка при обращении в поддержку. Пожалуйста, попробуйте позже.")
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
        await message.answer("Не удалось отправить сообщение в поддержку. Пожалуйста, попробуйте позже.")


# Регистрация обработчика сообщений от пользователей
dp.message.register(handle_user_message, lambda message: message.chat.type == ChatType.PRIVATE)


# Обработчик ответов от техподдержки
async def handle_support_reply(message: Message):
    # Добавляем проверку, чтобы игнорировать сообщения, отправленные ботом
    if message.from_user.is_bot:
        return

    if message.message_thread_id:
        # Ищем пользователя по теме
        user_id = None
        for uid, topic_id in user_topics.items():
            if topic_id == message.message_thread_id:
                user_id = uid
                break

        if user_id:
            # Отправляем ответ поддержки клиенту
            try:
                if message.content_type == ContentType.TEXT:
                    await bot.send_message(
                        chat_id=user_id,
                        text=message.text
                    )
                elif message.content_type == ContentType.PHOTO:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=message.photo[-1].file_id,
                        caption=message.caption
                    )
                elif message.content_type == ContentType.DOCUMENT:
                    await bot.send_document(
                        chat_id=user_id,
                        document=message.document.file_id,
                        caption=message.caption
                    )
                elif message.content_type == ContentType.VIDEO:
                    await bot.send_video(
                        chat_id=user_id,
                        video=message.video.file_id,
                        caption=message.caption
                    )
                elif message.content_type == ContentType.VOICE:
                    await bot.send_voice(
                        chat_id=user_id,
                        voice=message.voice.file_id,
                        caption=message.caption
                    )
                elif message.content_type == ContentType.STICKER:
                    await bot.send_sticker(
                        chat_id=user_id,
                        sticker=message.sticker.file_id
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text="Получено сообщение от поддержки, но этот тип сообщения не поддерживается."
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения клиенту: {e}")
        else:
            logger.error("Не найден пользователь для данной темы")


# Регистрация обработчика ответов от техподдержки
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


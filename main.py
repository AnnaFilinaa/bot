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

API_TOKEN="7306703210:AAGaafa05SGa9loovceBZXor1TZWfd-3s4Q"
SUPPORT_GROUP_ID="-1002364803574"


# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем бота с указанием DefaultBotProperties для HTML-разметки
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Файл для хранения соответствия пользователей и ID тем
USER_TOPICS_FILE = 'user_topics.json'

# Словарь для хранения соответствия пользователей и ID тем
user_topics = {}


# Функция для загрузки соответствия из файла
def load_user_topics():
    global user_topics
    if os.path.exists(USER_TOPICS_FILE):
        with open(USER_TOPICS_FILE, 'r') as f:
            user_topics = json.load(f)
            # Ключи в JSON-файле сохраняются как строки, поэтому преобразуем их в int
            user_topics = {int(k): v for k, v in user_topics.items()}
    else:
        user_topics = {}


# Функция для сохранения соответствия в файл
def save_user_topics():
    with open(USER_TOPICS_FILE, 'w') as f:
        json.dump(user_topics, f)


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
    user_username = message.from_user.username
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"

    # Формируем название темы из имени и никнейма
    if user_username:
        topic_name = f"{user_name} | @{user_username}"
    else:
        topic_name = f"{user_name}"

    # Проверяем, есть ли уже тема для этого пользователя
    if user_id not in user_topics:
        try:
            # Создаем новую тему в группе поддержки
            topic = await bot.create_forum_topic(
                chat_id=SUPPORT_GROUP_ID,
                name=topic_name
            )
            topic_id = topic.message_thread_id
            user_topics[user_id] = topic_id
            save_user_topics()  # Сохраняем соответствие в файл

            # Отправляем ссылку на профиль пользователя в тему поддержки (только при создании темы)
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
    else:
        topic_id = user_topics[user_id]

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
    # Загрузка соответствия из файла при запуске бота
    load_user_topics()

    try:
        chat = await bot.get_chat(SUPPORT_GROUP_ID)
        logger.info(f"Бот успешно получил доступ к группе: {chat.title}")
    except Exception as e:
        logger.error(f"Ошибка доступа к группе: {e}")
        return

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())


from aiogram import Dispatcher, Bot, types, executor
from aiogram.utils.callback_data import CallbackData
from aiogram.types import ParseMode
from aiogram.utils.exceptions import MessageToEditNotFound, MessageNotModified, BotBlocked

import database
import olimpiada
import config
import asyncio


import logging
logging.basicConfig(filename="exceptions.log", filemode="w")

bot = Bot(token=config.bot_token, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher(bot)

# type может быть либо add, либо remove
swap_tag_cb = CallbackData("swap_tag", "id", "type")
all_tags_cb = CallbackData("all_tags", "type")

# type может быть либо full, либо short
news_cb = CallbackData("news", "post_id", "type")


async def ping_admin():
    await bot.send_message(config.admin_id, "Алё, есть проблемы. Чекни логи и всё будет нормально) /log")


@dp.message_handler(commands="start")
async def cmd_start(msg: types.Message):
    user_id = msg.from_user.id
    if await database.user_exists(user_id):
        await msg.answer("Доброго времени суток!")
        await msg.answer("Если у вас что-то не получается, то попробуйте команду /help")
    else:
        await database.execute("INSERT INTO users (user_id) values ($1)", user_id)
        await msg.answer("Привет!")
        await msg.answer("Данный бот поможет вам следить за олимпиадами.")
        await msg.answer("Так как вы здесь впервые, то нужно воспользоваться командами /filter и /?")
        ############################################## Создать канал ####################################################?


async def get_tags(user_id):
    user_tags = await database.get_user_tags(user_id)
    tag_list = config.tag_list
    text = "Перед вами список предметов, по которым будут сортироваться новости с сайта olimpiada.ru\n\n" \
           "✅ *Галочкой* отмечаются те предметы, которые вы выбрали.\n\n" \
           "Чтобы добавить или удалить предмет, нужно нажать на соответсвующую кнопку.\n\n" \
           "Новость будет вам показываться, если она относится хотя бы к одному из выбранных предметов.\n\n" \
           "Значит, если вы *ничего не выбрали,* то вы *не будете* видеть новости."
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    for ind in range(len(tag_list)):
        if user_tags & (1 << ind):
            keyboard.insert(
                types.InlineKeyboardButton("✅ " + tag_list[ind], callback_data=swap_tag_cb.new(id=ind, type="remove")))
        else:
            keyboard.insert(
                types.InlineKeyboardButton(tag_list[ind], callback_data=swap_tag_cb.new(id=ind, type="add")))

    # добавляем кнопку, если уже все предметы не выбраны
    if user_tags != (1 << len(tag_list)) - 1:
        keyboard.insert(types.InlineKeyboardButton("➕ Добавить все", callback_data=all_tags_cb.new(type="add")))
    # добавляем кнопку, если выбран хотя бы один предмет
    if user_tags != 0:
        keyboard.insert(types.InlineKeyboardButton("➖ Очистить все", callback_data=all_tags_cb.new(type="remove")))

    return text, keyboard


async def send_filter_msg(user_id):
    if await database.fetchrow("SELECT message_id FROM filter_messages WHERE user_id = $1", user_id) is not None:
        record = await database.fetchrow("SELECT message_id FROM filter_messages WHERE user_id = $1", user_id)
        message_id = record["message_id"]
        await database.execute("DELETE FROM filter_messages WHERE user_id = $1", user_id)
        await bot.delete_message(user_id, message_id)
    text, keyboard = await get_tags(user_id)
    sent_msg = await bot.send_message(user_id, text, reply_markup=keyboard)
    await database.execute("INSERT INTO filter_messages (user_id, message_id) values ($1, $2)", user_id,
                           sent_msg.message_id)


@dp.message_handler(commands="filter")
async def cmd_filter(msg: types.Message):
    user_id = msg.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values ($1)", user_id)
    await send_filter_msg(user_id)


@dp.callback_query_handler(swap_tag_cb.filter())
async def query_swap_tag(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values ($1)", user_id)

    tag_id = callback_data["id"]

    if callback_data["type"] == "add":
        await database.execute("UPDATE users SET tags = tags | $1 WHERE user_id = $2", (1 << int(tag_id)), user_id)
    else:
        await database.execute("UPDATE users SET tags = tags - $1 WHERE user_id = $2", (1 << int(tag_id)), user_id)
    text, keyboard = await get_tags(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except MessageToEditNotFound:
        await send_filter_msg(user_id)
    except Exception as error:
        logging.exception(error)
        await ping_admin()


@dp.callback_query_handler(all_tags_cb.filter())
async def query_all_tags(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values ($1)", user_id)
        await bot.send_message(user_id, "По каким-то обстоятельствам, вы были удалены из базы данных, "
                                        "поэтому ваши настройки в фильтре были сброшены")
    cnt_tags = len(config.tag_list)

    if callback_data["type"] == "add":
        await database.execute("UPDATE users SET tags = $1 WHERE user_id = $2", (1 << cnt_tags) - 1, user_id)
    else:
        await database.execute("UPDATE users SET tags = 0 WHERE user_id = $1", user_id)
    text, keyboard = await get_tags(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except MessageToEditNotFound:
        await send_filter_msg(user_id)
    except Exception as error:
        logging.exception(error)
        await ping_admin()


async def insert_post(post: olimpiada.Post):
    while (await database.fetchrow("SELECT count(*) FROM saved_posts"))["count"] > 1000:
        min_post_id = (await database.fetchrow("SELECT min(post_id) FROM saved_posts"))["min"]
        await database.execute("DELETE FROM saved_posts WHERE post_id = $1", min_post_id)
    await database.execute("INSERT INTO saved_posts (post_id, head, text, olimp, tags) VALUES ($1, $2, $3, $4, $5)",
                           post.post_id, post.head, post.text, post.olimp, post.tags)


@dp.callback_query_handler(news_cb.filter())
async def query_news(query: types.CallbackQuery, callback_data: dict):
    post_id = int(callback_data["post_id"])
    downloading_keyboard = types.InlineKeyboardMarkup()
    downloading_keyboard.add(types.InlineKeyboardButton(text="Загрузка...", callback_data="None"))
    try:
        if await database.fetchrow("SELECT post_id FROM saved_posts WHERE post_id = $1", post_id) is not None:
            record = await database.fetchrow("SELECT * FROM saved_posts WHERE post_id = $1", post_id)
            post = olimpiada.Post(post_id, record["head"], record["text"], record["olimp"], record["tags"])
        else:
            await query.message.edit_reply_markup(downloading_keyboard)
            post = await olimpiada.get_post(post_id)
            await insert_post(post)
        if callback_data["type"] == "full":
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("⇧Убрать текст", callback_data=news_cb.new(post_id=post_id, type="short")))
            await query.message.edit_text(text=post.full_text(), reply_markup=keyboard, disable_web_page_preview=True)
        else:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("⇩Полный текст", callback_data=news_cb.new(post_id=post_id, type="full")))
            await query.message.edit_text(text=post.short_text(), reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as error:
        logging.exception(error)


async def news():
    while True:
        post_id = (await database.fetchrow("SELECT max(post_id) FROM saved_posts"))["max"]
        post_id += 1

        try:
            post = await olimpiada.get_post(post_id)
        except Exception as error:
            await bot.send_message(config.admin_id, f"Какая-то проблема с получением новости {post_id}")
            logging.exception(error)
            await ping_admin()
            await asyncio.sleep(3600)
            break

        if post is None:
            await asyncio.sleep(3600)
            break

        await insert_post(post)

        text = post.short_text()
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("⇩Полный текст", callback_data=news_cb.new(post_id=post_id, type="full")))

        tag_list = config.tag_list
        news_tags = 0

        for ind in range(len(tag_list)):
            if tag_list[ind] in post.tags:
                news_tags |= (1 << ind)

        for record in await database.fetch("SELECT user_id FROM users WHERE tags | $1 != 0", news_tags):
            user_id = record["user_id"]
            try:
                await bot.send_message(user_id, text=text, reply_markup=keyboard, disable_web_page_preview=True)
            except BotBlocked:
                try:
                    await database.execute(f"DELETE from users WHERE user_id = $1", user_id)
                    logging.warning(f"Deleted user with user_id = {user_id}")
                except Exception as error:
                    logging.exception(error)
                    await ping_admin()

            except Exception as error:
                logging.exception(error)
                await ping_admin()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(news())
    executor.start_polling(dp, skip_updates=True)

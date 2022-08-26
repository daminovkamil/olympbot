import requests
from aiogram import Dispatcher, Bot, types, executor
from aiogram.utils.callback_data import CallbackData
from aiogram.types import ParseMode
from aiogram.utils.exceptions import MessageToEditNotFound, MessageNotModified, BotBlocked
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

import database
import olimpiada
import config
import asyncio
import atexit
import logging

logging.basicConfig(filename="exceptions.log", filemode="w")

bot = Bot(token=config.bot_token, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
dp = Dispatcher(bot, storage=MemoryStorage())

# type может быть либо add, либо remove
swap_tag_cb = CallbackData("swap_tag", "id", "type")
all_tags_cb = CallbackData("all_tags", "type")

# type может быть либо full, либо short
news_cb = CallbackData("news", "post_id", "type")

olymp_cb = CallbackData("olymp", "type")


class OlympForm(StatesGroup):
    add_olymp = State()
    remove_olymp = State()


@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(msg: types.Message, state: FSMContext):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    async with state.proxy() as data:
        try:
            await bot.delete_message(user_id, data["message_id"])
        except:
            pass
    try:
        await msg.delete()
    except:
        pass
    await state.finish()


async def ping_admin():
    await bot.send_message(config.admin_id, "Советую посмотреть логи) У кого-то что-то сломалось")


@dp.message_handler(commands="start")
async def cmd_start(msg: types.Message):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    if await database.user_exists(user_id):
        await msg.answer("Доброго времени суток!")
    else:
        await database.execute(f"INSERT INTO users (user_id) values (%s)", (user_id,))
        await msg.answer("Привет!")
        await msg.answer("Данный неофициальный бот поможет вам следить за олимпиадами.")
        await msg.answer("Поддерживаются две команды:\n"
                         "/filter - настройка фильтра новостей\n"
                         "/olymp - список олимпиад для напоминаний")


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
    if await database.fetchrow(f"SELECT message_id FROM filter_messages WHERE user_id = %s", (user_id,)) is not None:
        message_id = await database.fetchrow(f"SELECT message_id FROM filter_messages WHERE user_id = %s", (user_id,))
        await database.execute(f"DELETE FROM filter_messages WHERE user_id = %s", (user_id,))
        await bot.delete_message(user_id, message_id)
    text, keyboard = await get_tags(user_id)
    sent_msg = await bot.send_message(user_id, text, reply_markup=keyboard)
    await database.execute("INSERT INTO filter_messages (user_id, message_id) values (%s, %s)",
                           (user_id, sent_msg.message_id))


async def get_olymp_msg(user_id):
    activities = await database.fetchrow("SELECT activities FROM users WHERE user_id = %s", (user_id,))
    keyboard = types.InlineKeyboardMarkup()
    if len(activities) <= 34:
        keyboard.insert(types.InlineKeyboardButton("➕ Добавить олимпиаду", callback_data=olymp_cb.new(type="add")))
    if activities:
        text = "Вы выбрали следующие олимпиады:\n\n"
        for activity_id in activities:
            activity_name = await database.fetchrow("SELECT activity_name FROM cool_olympiads WHERE activity_id = %s",
                                                    (activity_id,))
            text += f"<code>{activity_id}</code>   " \
                    f"<a href=\"https://olimpiada.ru/activity/{activity_id}\">{activity_name}</a>\n\n"
        keyboard.insert(types.InlineKeyboardButton("❌ Удалить олимпиаду", callback_data=olymp_cb.new(type="remove")))
    else:
        text = "Пока вы не выбрали никакую олимпиаду\n\n" \
               "Чтобы получать уведомления о разных событиях, " \
               "связанных с какой олимпиадой, например, " \
               "\"начало отборочного этапа\", нажмите на кнопку ниже"
    return text, keyboard


@dp.message_handler(commands="olymp")
async def cmd_olymp(msg: types.Message):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))
    text, keyboard = await get_olymp_msg(user_id)
    await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="html")


@dp.callback_query_handler(olymp_cb.filter())
async def query_olymp(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    user_id = query.from_user.id
    if callback_data["type"] == "add":
        if await database.fetchrow("SELECT array_length(activities, 1) FROM users WHERE user_id = %s",
                                   (user_id,)) == 35:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id, text=text,
                                        reply_markup=keyboard, parse_mode="html")
            return
        await OlympForm.add_olymp.set()
        text = "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        msg = await bot.send_message(user_id, text)
        async with state.proxy() as data:
            data["message_id"] = msg.message_id
            data["main_message_id"] = query.message.message_id
    else:
        if await database.fetchrow("SELECT array_length(activities, 1) FROM users WHERE user_id = %s",
                                   (user_id,)) is None:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id, text=text,
                                        reply_markup=keyboard, parse_mode="html")
            return
        await OlympForm.remove_olymp.set()
        text = "Пожалуйста, введите *номер* олимпиады, которую хотите удалить из списка.\n\n" \
               "Для отмены запроса, используйте /cancel"
        msg = await bot.send_message(user_id, text)
        async with state.proxy() as data:
            data["message_id"] = msg.message_id
            data["main_message_id"] = query.message.message_id


@dp.message_handler(content_types="text", state=OlympForm.remove_olymp.state)
async def adding_olymp(msg: types.Message, state: FSMContext):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))
    async with state.proxy() as data:
        try:
            await bot.delete_message(user_id, data["message_id"])
        except:
            pass
    try:
        await msg.delete()
    except:
        pass
    if not msg.text.isdigit():
        text = "*Ошибка* ‼️*Ввод должен состоять из цифр* ‼\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите удалить из списка.\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    activity_id = int(msg.text)
    if await database.fetchrow("SELECT user_id FROM users WHERE user_id = %s AND %s = ANY(activities)",
                               (user_id, activity_id)) is None:
        text = "*Ошибка* ‼️*Такой олимпиады нет в вашем списке (проверьте /olymp)* ‼\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите удалить из списка.\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    await database.execute("UPDATE users SET activities = array_remove(activities, %s)", (activity_id,))
    async with state.proxy() as data:
        try:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=data["main_message_id"], text=text,
                                        reply_markup=keyboard, parse_mode="html")
        except:
            pass
    await state.finish()


@dp.message_handler(content_types="text", state=OlympForm.add_olymp.state)
async def removing_olymp(msg: types.Message, state: FSMContext):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))
    async with state.proxy() as data:
        try:
            await bot.delete_message(user_id, data["message_id"])
        except:
            pass
    try:
        await msg.delete()
    except:
        pass
    if not msg.text.isdigit():
        text = "*Ошибка* ‼️*Ввод должен состоять из цифр* ‼\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    activity_id = int(msg.text)
    if not await olimpiada.check_olympiad(activity_id):
        text = f"*Ошибка* ‼️Данное число не является номером, либо на странице https://olimpiada.ru/activity/{activity_id} " \
               f"нет поля *«Расписание»*\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    if await database.fetchrow("SELECT activity_id FROM cool_olympiads WHERE activity_id = %s", (activity_id,)) is None:
        text = "*Ошибка* ‼️*Данной олимпиады нет в базе данных* ‼ Возможно олимпиада, " \
               "которую вы пытаетесь  добавить не входит в перечень" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    if await database.fetchrow("SELECT user_id FROM users WHERE user_id = %s AND %s = ANY(activities)",
                               (user_id, activity_id)) is not None:
        text = "*Ошибка* ‼️*Вы и так выбрали данную олимпиаду* ‼\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    await database.execute("UPDATE users SET activities = array_append(activities, %s) WHERE user_id = %s",
                           (activity_id, user_id))
    async with state.proxy() as data:
        try:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=data["main_message_id"], text=text,
                                        reply_markup=keyboard, parse_mode="html")
        except:
            pass
    await state.finish()


@dp.message_handler(commands="filter")
async def cmd_filter(msg: types.Message):
    if msg.from_user.id != msg.chat.id:
        await msg.answer("Извините, но бот пока не работает в группах.")
        await bot.leave_chat(msg.chat.id)
        return
    user_id = msg.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))
    await send_filter_msg(user_id)


@dp.callback_query_handler(swap_tag_cb.filter())
async def query_swap_tag(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    if not await database.user_exists(user_id):
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))

    tag_id = int(callback_data["id"])

    if callback_data["type"] == "add":
        await database.execute("UPDATE users SET tags = tags | %s WHERE user_id = %s", (1 << tag_id, user_id))
    else:
        await database.execute("UPDATE users SET tags = tags - %s WHERE user_id = %s", (1 << tag_id, user_id))
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
        await database.execute("INSERT INTO users (user_id) values (%s)", (user_id,))
        await bot.send_message(user_id, "По каким-то обстоятельствам, вы были удалены из базы данных, "
                                        "поэтому ваши настройки в фильтре были сброшены")
    cnt_tags = len(config.tag_list)

    if callback_data["type"] == "add":
        await database.execute("UPDATE users SET tags = %s WHERE user_id = %s", ((1 << cnt_tags) - 1, user_id))
    else:
        await database.execute("UPDATE users SET tags = 0 WHERE user_id = %s", (user_id,))
    text, keyboard = await get_tags(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except MessageToEditNotFound:
        await send_filter_msg(user_id)
    except Exception as error:
        logging.exception(error)
        await ping_admin()


async def insert_post(post: olimpiada.Post):
    while await database.fetchrow("SELECT count(*) FROM saved_posts") > 1000:
        min_post_id = await database.fetchrow("SELECT min(post_id) FROM saved_posts")
        await database.execute("DELETE FROM saved_posts WHERE post_id = %s", (min_post_id,))
    for activity_id in post.olimp:
        if await database.fetchrow("SELECT activity_id FROM cool_olympiads WHERE activity_id = %s", (activity_id,)):
            post.head = "⭐ " + post.head
            break
    await database.execute("INSERT INTO saved_posts (post_id, head, text, olimp, tags) VALUES (%s, %s, %s, %s, %s)",
                           (post.post_id, post.head, post.text, post.olimp, post.tags))


@dp.callback_query_handler(news_cb.filter())
async def query_news(query: types.CallbackQuery, callback_data: dict):
    post_id = int(callback_data["post_id"])
    downloading_keyboard = types.InlineKeyboardMarkup()
    downloading_keyboard.add(types.InlineKeyboardButton(text="Загрузка...", callback_data="None"))
    try:
        if await database.fetchrow(f"SELECT post_id FROM saved_posts WHERE post_id = %s", (post_id,)) is not None:
            record = await database.fetchrow(f"SELECT head, text, olimp, tags FROM saved_posts WHERE post_id = %s",
                                             (post_id,))
            post = olimpiada.Post(post_id, record[0], record[1], record[2], record[3])
        else:
            await query.message.edit_reply_markup(downloading_keyboard)
            post = await olimpiada.get_post(post_id)
            await insert_post(post)
        if callback_data["type"] == "full":
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("⇧Убрать текст", callback_data=news_cb.new(post_id=post_id, type="short")))
            await query.message.edit_text(text=post.full_text(), reply_markup=keyboard)
        else:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("⇩Полный текст", callback_data=news_cb.new(post_id=post_id, type="full")))
            await query.message.edit_text(text=post.short_text(), reply_markup=keyboard)
    except Exception as error:
        logging.exception(error)
        await ping_admin()


async def try_send(*args, **kwargs):
    try:
        await bot.send_message(*args, **kwargs)
    except Exception as error:
        logging.exception(error)
        await ping_admin()


async def news():
    while True:
        post_id = await database.fetchrow("SELECT max(post_id) FROM saved_posts")
        post_id += 1

        try:
            post = await olimpiada.get_post(post_id)
        except Exception as error:
            await bot.send_message(config.admin_id, f"Какая-то проблема с получением новости {post_id}")
            logging.exception(error)
            await ping_admin()
            await asyncio.sleep(3600)
            continue

        if post is None:
            await asyncio.sleep(3600)
            continue

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

        for user_id in await database.fetch("SELECT user_id FROM users WHERE tags | %s != 0", (news_tags,)):
            await try_send(user_id, text=text, reply_markup=keyboard)


async def downloading_events():
    while True:
        try:
            for activity_id in await database.fetch("SELECT activity_id FROM cool_olympiads"):
                for event in await olimpiada.get_events(activity_id):
                    if await database.fetchrow(
                            "SELECT activity_id FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
                            (activity_id, event.event_id)) is None:
                        await database.execute(
                            "INSERT INTO olympiad_events (activity_id, event_id, event_name, first_date, second_date) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (event.activity_id, event.event_id, event.event_name, event.first_date, event.second_date))
                await asyncio.sleep(1000)
            await database.execute("DELETE FROM olympiad_events WHERE (second_date IS NOT NULL AND "
                                   "second_date < CURRENT_DATE) OR (second_date IS NULL AND first_date < CURRENT_DATE)")
        except Exception as error:
            logging.exception(error)
            await ping_admin()
        await asyncio.sleep(1000)


async def events():
    while True:
        for event_name, event_id, activity_id in await database.fetch(
                "SELECT event_name, event_id, activity_id FROM olympiad_events WHERE "
                "first_date - 1 = CURRENT_DATE AND stage != 1"):
            await database.execute("UPDATE olympiad_events SET stage = 1 "
                                   "WHERE event_id = %s AND activity_id = %s",
                                   (event_id, activity_id))
            for user_id in await database.fetch("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                try:
                    activity_name = await database.fetchrow(
                        "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                    activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                    text = f"*Через день* {event_name.lower()}\n" \
                           f"[{activity_name}]({activity_link})"
                    await bot.send_message(user_id, text)
                except BotBlocked:
                    try:
                        await database.execute("DELETE from users WHERE user_id = %s", (user_id,))
                        logging.warning(f"Deleted user with user_id = {user_id}")
                    except Exception as error:
                        logging.exception(error)
                        await ping_admin()
                except Exception as error:
                    logging.exception(error)
                    await ping_admin()
        for event_name, event_id, activity_id in await database.fetch(
                "SELECT event_name, event_id, activity_id FROM olympiad_events WHERE "
                "first_date - 3 = CURRENT_DATE AND stage != 2"):
            await database.execute("UPDATE olympiad_events SET stage = 2 "
                                   "WHERE event_id = %s AND activity_id = %s",
                                   (event_id, activity_id))
            for user_id in await database.fetch("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                activity_name = await database.fetchrow(
                    "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                text = f"*Через 3 дня* {event_name.lower()}\n" \
                       f"[{activity_name}]({activity_link})"
                await try_send(user_id, text)
        for event_name, event_id, activity_id in await database.fetch(
                "SELECT event_name, event_id, activity_id FROM olympiad_events WHERE "
                "first_date - 7 = CURRENT_DATE AND stage != 3"):
            await database.execute("UPDATE olympiad_events SET stage = 3 "
                                   "WHERE event_id = %s AND activity_id = %s",
                                   (event_id, activity_id))
            for user_id in await database.fetch("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                activity_name = await database.fetchrow(
                    "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                text = f"*Через неделю* {event_name.lower()}\n" \
                       f"[{activity_name}]({activity_link})"
                await try_send(user_id, text)
        await asyncio.sleep(3600)


def say_hello():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.send_message(config.admin_id, "Запуск 🚀 Бот начал работать))"))


def say_bye():
    bot_token = config.bot_token
    chat_id = config.admin_id
    text = "Внимание ‼ Бот перестал работать(("
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    say_hello()
    atexit.register(say_bye)
    loop.create_task(news())
    loop.create_task(events())
    loop.create_task(downloading_events())
    executor.start_polling(dp, skip_updates=True)

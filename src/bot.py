import requests
from aiogram import Dispatcher, Bot, types, executor
from aiogram.utils.callback_data import CallbackData
from aiogram.types import ParseMode, ContentTypes
from aiogram.utils.exceptions import MessageToEditNotFound, MessageCantBeDeleted, BotBlocked, UserDeactivated
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types.web_app_info import WebAppInfo

import postgres
import olimpiada
import config
import asyncio
import logging
import datetime

bot = Bot(token=config.bot_token, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
dp = Dispatcher(bot, storage=MemoryStorage())
db = postgres.Postgres(config.database_url)

# type может быть либо add, либо remove
swap_tag_cb = CallbackData("swap_tag", "id", "type")
all_tags_cb = CallbackData("all_tags", "type")

# type может быть либо full, либо short
full_text_cb = CallbackData("full_text", "post_id")
short_text_cb = CallbackData("short_text", "post_id")

olymp_cb = CallbackData("olymp", "type")


class OlympForm(StatesGroup):
    add_olymp = State()
    remove_olymp = State()


@dp.message_handler(content_types='web_app_data')
async def getting_web_data(msg: types.WebAppData):
    print(msg)


def user_exists(user_id: int):
    return db.one("SELECT user_id FROM users WHERE user_id = %s", (user_id,)) is not None


def get_user_tags(user_id: int):
    return db.one("SELECT tags FROM users WHERE user_id = %s", (user_id,))


@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(msg: types.Message, state: FSMContext):
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


def ping_admin(text="Советую посмотреть логи) У кого-то что-то сломалось"):
    bot_token = config.bot_token
    chat_id = config.admin_id
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


@dp.message_handler(commands="start")
async def cmd_start(msg: types.Message):
    user_id = msg.from_user.id
    if user_exists(user_id):
        await msg.answer("Доброго времени суток!")
    else:
        db.run(f"INSERT INTO users (user_id) values (%s)", (user_id,))
        await msg.answer("Привет!")
        await msg.answer("Данный неофициальный бот поможет вам следить за олимпиадами.")
        await msg.answer("Поддерживаются две команды:\n"
                         "/filter - настройка фильтра новостей\n"
                         "/olymp - список олимпиад для напоминаний")


async def get_tags(user_id):
    user_tags = get_user_tags(user_id)
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
    if db.one(f"SELECT message_id FROM filter_messages WHERE user_id = %s", (user_id,)) is not None:
        message_id = db.one(f"SELECT message_id FROM filter_messages WHERE user_id = %s", (user_id,))
        db.run(f"DELETE FROM filter_messages WHERE user_id = %s", (user_id,))
        try:
            await bot.delete_message(user_id, message_id)
        except MessageCantBeDeleted:
            pass
        except Exception as error:
            logging.exception(error)
    text, keyboard = await get_tags(user_id)
    sent_msg = await bot.send_message(user_id, text, reply_markup=keyboard)
    db.run("INSERT INTO filter_messages (user_id, message_id) values (%s, %s)",
           (user_id, sent_msg.message_id))


async def get_olymp_msg(user_id):
    activities = db.one("SELECT activities FROM users WHERE user_id = %s", (user_id,))
    keyboard = types.InlineKeyboardMarkup()
    if len(activities) <= 34:
        keyboard.insert(types.InlineKeyboardButton("➕ Добавить олимпиаду", callback_data=olymp_cb.new(type="add")))
    if activities:
        text = "Вы выбрали следующие олимпиады:\n\n"
        for activity_id in activities:
            activity_name = db.one("SELECT activity_name FROM cool_olympiads WHERE activity_id = %s",
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
    user_id = msg.from_user.id
    if not user_exists(user_id):
        db.run("INSERT INTO users (user_id) values (%s)", (user_id,))
    text, keyboard = await get_olymp_msg(user_id)
    ans: types.Message = await bot.send_message(user_id, text, parse_mode="html")
    keyboard.add(
        types.InlineKeyboardButton(
            text="Изменить через WebApp",
            web_app=WebAppInfo(
                url=f"https://kdaminov.ru/{config.secret_url}{user_id}?message_id={ans.message_id}"
            )
        )
    )
    await ans.edit_reply_markup(reply_markup=keyboard)


@dp.callback_query_handler(olymp_cb.filter())
async def query_olymp(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    user_id = query.from_user.id
    if callback_data["type"] == "add":
        if db.one("SELECT array_length(activities, 1) FROM users WHERE user_id = %s",
                  (user_id,)) == 35:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id, text=text,
                                        parse_mode="html")
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
        if db.one("SELECT array_length(activities, 1) FROM users WHERE user_id = %s",
                  (user_id,)) is None:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id, text=text,
                                        parse_mode="html")
            return
        await OlympForm.remove_olymp.set()
        text = "Пожалуйста, введите *номер* олимпиады, которую хотите удалить из списка.\n\n" \
               "Для отмены запроса, используйте /cancel"
        msg = await bot.send_message(user_id, text)
        async with state.proxy() as data:
            data["message_id"] = msg.message_id
            data["main_message_id"] = query.message.message_id


@dp.message_handler(content_types="text", state=OlympForm.remove_olymp.state)
async def removing_olymp(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    if not user_exists(user_id):
        db.run("INSERT INTO users (user_id) values (%s)", (user_id,))
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
    if db.one("SELECT user_id FROM users WHERE user_id = %s AND %s = ANY(activities)",
              (user_id, activity_id)) is None:
        text = "*Ошибка* ‼️*Такой олимпиады нет в вашем списке (проверьте /olymp)* ‼\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите удалить из списка.\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    db.run("UPDATE users SET activities = array_remove(activities, %s)", (activity_id,))
    async with state.proxy() as data:
        try:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=data["main_message_id"], text=text,
                                        parse_mode="html")
        except:
            pass
    await state.finish()


@dp.message_handler(content_types="text", state=OlympForm.add_olymp.state)
async def adding_olymp(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    if not user_exists(user_id):
        db.run("INSERT INTO users (user_id) values (%s)", (user_id,))
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
    if db.one("SELECT activity_id FROM cool_olympiads WHERE activity_id = %s", (activity_id,)) is None:
        text = "*Ошибка* ‼️*Данной олимпиады нет в базе данных* ‼ Возможно олимпиада, " \
               "которую вы пытаетесь  добавить не входит в перечень.\n\n" \
               "Пожалуйста, введите *номер* олимпиады, которую хотите добавить.\n\n" \
               "Номер олимпиады можно получить из ссылки на сайте:\n" \
               "https://olimpiada.ru/activity/*номер*\n\n" \
               "Для отмены запроса, используйте /cancel"
        answer = await msg.answer(text)
        async with state.proxy() as data:
            data["message_id"] = answer.message_id
        return
    if db.one("SELECT user_id FROM users WHERE user_id = %s AND %s = ANY(activities)",
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
    db.run("UPDATE users SET activities = array_append(activities, %s) WHERE user_id = %s",
           (activity_id, user_id))
    async with state.proxy() as data:
        try:
            text, keyboard = await get_olymp_msg(user_id)
            await bot.edit_message_text(chat_id=user_id, message_id=data["main_message_id"], text=text,
                                        parse_mode="html")
        except:
            pass
    await state.finish()


@dp.message_handler(commands="filter")
async def cmd_filter(msg: types.Message):
    user_id = msg.from_user.id
    if not user_exists(user_id):
        db.run("INSERT INTO users (user_id) values (%s)", (user_id,))
    await send_filter_msg(user_id)


@dp.callback_query_handler(swap_tag_cb.filter())
async def query_swap_tag(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    if not user_exists(user_id):
        db.run("INSERT INTO users (user_id) values (%s)", (user_id,))
    tag_id = int(callback_data["id"])
    if callback_data["type"] == "add":
        db.run("UPDATE users SET tags = tags | %s WHERE user_id = %s", (1 << tag_id, user_id))
    else:
        db.run("UPDATE users SET tags = tags - %s WHERE user_id = %s", (1 << tag_id, user_id))
    text, keyboard = await get_tags(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except MessageToEditNotFound:
        await send_filter_msg(user_id)
    except Exception as error:
        logging.exception(error)
        ping_admin()


@dp.callback_query_handler(all_tags_cb.filter())
async def query_all_tags(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    cnt_tags = len(config.tag_list)
    if callback_data["type"] == "add":
        db.run("UPDATE users SET tags = %s WHERE user_id = %s", ((1 << cnt_tags) - 1, user_id))
    else:
        db.run("UPDATE users SET tags = 0 WHERE user_id = %s", (user_id,))
    text, keyboard = await get_tags(user_id)
    try:
        await query.message.edit_reply_markup(reply_markup=keyboard)
    except MessageToEditNotFound:
        await send_filter_msg(user_id)
    except Exception as error:
        logging.exception(error)
        ping_admin()


@dp.callback_query_handler(full_text_cb.filter())
async def query_full_text(query: types.CallbackQuery, callback_data: dict):
    post_id = int(callback_data["post_id"])
    downloading_keyboard = types.InlineKeyboardMarkup()
    downloading_keyboard.add(types.InlineKeyboardButton(text="Загрузка...", callback_data="None"))
    try:
        await query.message.edit_reply_markup(downloading_keyboard)
        post = await olimpiada.get_post(post_id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("⇧Убрать текст", callback_data=short_text_cb.new(post_id=post_id)))
        await query.message.edit_text(text=post.full_text(), reply_markup=keyboard)
    except Exception as error:
        logging.exception(error)
        ping_admin()


@dp.callback_query_handler(short_text_cb.filter())
async def query_short_text(query: types.CallbackQuery, callback_data: dict):
    post_id = int(callback_data["post_id"])
    downloading_keyboard = types.InlineKeyboardMarkup()
    downloading_keyboard.add(types.InlineKeyboardButton(text="Загрузка...", callback_data="None"))
    try:
        await query.message.edit_reply_markup(downloading_keyboard)
        post = await olimpiada.get_post(post_id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("⇩Полный текст", callback_data=full_text_cb.new(post_id=post_id)))
        await query.message.edit_text(text=post.short_text(), reply_markup=keyboard)
    except Exception as error:
        logging.exception(error)
        ping_admin()


async def try_send(*args, **kwargs):
    try:
        await bot.send_message(*args, **kwargs)
    except BotBlocked:
        if "chat_id" in kwargs:
            user_id = kwargs["chat_id"]
        else:
            user_id = args[0]
        db.run("UPDATE users SET tags = 0 WHERE user_id = %s", (user_id,))
        db.run("UPDATE users SET activities = '{}' WHERE user_id = %s", (user_id,))
    except UserDeactivated:
        if "chat_id" in kwargs:
            user_id = kwargs["chat_id"]
        else:
            user_id = args[0]
        db.run("UPDATE users SET tags = 0 WHERE user_id = %s", (user_id,))
        db.run("UPDATE users SET activities = '{}' WHERE user_id = %s", (user_id,))
    except Exception as error:
        logging.exception(error)
        ping_admin()


async def news():
    while True:
        post_id = db.one("SELECT post_id FROM last_post")
        post_id += 1

        try:
            post = await olimpiada.get_post(post_id)
        except Exception as error:
            logging.exception(error)
            ping_admin(f"Какая-то проблема с получением новости {post_id}")
            await asyncio.sleep(3600)
            continue

        if post is None:
            await asyncio.sleep(3600)
            continue

        db.run("UPDATE last_post SET post_id = post_id + 1")

        text = post.short_text()
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("⇩Полный текст", callback_data=full_text_cb.new(post_id=post_id)))

        tag_list = config.tag_list
        news_tags = 0

        for ind in range(len(tag_list)):
            if tag_list[ind] in post.tags:
                news_tags |= (1 << ind)

        for user_id in db.all("SELECT user_id FROM users WHERE tags & %s != 0", (news_tags,)):
            await try_send(user_id, text=text, reply_markup=keyboard)


async def events():
    try:
        for activity_id in db.all("SELECT activity_id FROM cool_olympiads"):
            try:
                db_events = db.all("SELECT event_id FROM olympiad_events WHERE activity_id = %s", (activity_id,))
                current_events = []
                current_date = datetime.date.today()
                for event in await olimpiada.get_events(activity_id):
                    stage = db.one("SELECT stage FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
                                   (activity_id, event.event_id))
                    if stage is None:
                        db.run("INSERT INTO olympiad_events (activity_id, event_id) values (%s, %s)",
                               (activity_id, event.event_id))
                        stage = 0
                    if event.first_date is None:
                        continue

                    if stage != 1 and event.first_date - datetime.timedelta(days=1) == current_date:
                        db.run("UPDATE olympiad_events SET stage = 1 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in db.all("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                            activity_name = db.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через день* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    if stage != 2 and event.first_date - datetime.timedelta(days=3) == current_date:
                        db.run("UPDATE olympiad_events SET stage = 2 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in db.all("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                            activity_name = db.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через 3 дня* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    if stage != 3 and event.first_date - datetime.timedelta(days=7) == current_date:
                        db.run("UPDATE olympiad_events SET stage = 3 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in db.all("SELECT user_id FROM users WHERE %s = ANY(activities)", (activity_id,)):
                            activity_name = db.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через неделю* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    current_events.append(event.event_id)

                for event_id in db_events:
                    if event_id not in current_events:
                        db.run("DELETE FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event_id))
            except Exception as error:
                logging.exception(error)
                ping_admin(f"Проблемы с activity_id = {activity_id} в функции events")
            await asyncio.sleep(1)
    except Exception as error:
        logging.exception(error)
        ping_admin("Какая-то проблема с функцией events")
    await asyncio.sleep(3600)


if __name__ == "__main__":
    logging.basicConfig(filename="log", filemode="w")
    loop = asyncio.get_event_loop()
    loop.create_task(news())
    loop.create_task(events())
    executor.start_polling(dp, skip_updates=True)

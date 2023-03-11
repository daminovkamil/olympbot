import requests
from aiogram import Dispatcher, Bot, types, executor
from aiogram.utils.callback_data import CallbackData
from aiogram.types import ParseMode
from aiogram.utils.exceptions import BotBlocked, UserDeactivated
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.web_app_info import WebAppInfo
import json

import database
import olimpiada
import config
import asyncio
import logging
import datetime

bot = Bot(token=config.bot_token, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
dp = Dispatcher(bot, storage=MemoryStorage())


full_text_cb = CallbackData("full_text", "post_id")
short_text_cb = CallbackData("short_text", "post_id")


@dp.message_handler(content_types='web_app_data')
async def getting_web_data(msg: types.Message):
    user_id = msg.from_user.id
    user = database.User(user_id)
    web_app_data = msg.web_app_data
    if web_app_data.button_text == "Предметы":
        data = json.loads(web_app_data.data)
        user.subjects = data["subjects"]
        user.save()
    if web_app_data.button_text == "Олимпиады":
        data = json.loads(web_app_data.data)
        user.olympiads = data["olympiads"]
        user.save()
    if web_app_data.button_text == "Настройки":
        data = json.loads(web_app_data.data)
        user.news_enabled = data["news_enabled"]
        user.subjects_filter = data["subjects_filter"]
        user.olympiads_filter = data["olympiads_filter"]
        user.notifications_enabled = data["notifications_enabled"]
        user.save()
    try:
        await msg.delete()
    except Exception as error:
        logging.error(error)


def ping_admin(text="Советую посмотреть логи) У кого-то что-то сломалось"):
    bot_token = config.bot_token
    chat_id = config.admin_id
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


@dp.message_handler(commands="start")
async def cmd_start(msg: types.Message):
    user_id = msg.from_user.id

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    keyboard.insert(types.KeyboardButton(text="Предметы",
                                         web_app=WebAppInfo(url="https://olympbot.kdaminov.ru/subjects/%s" % user_id)))
    keyboard.insert(types.KeyboardButton(text="Олимпиады", web_app=WebAppInfo(url="https://olympbot.kdaminov.ru/olympiads/%s" % user_id)))
    keyboard.insert(types.KeyboardButton(text="Настройки", web_app=WebAppInfo(url="https://olympbot.kdaminov.ru/settings/%s" % user_id)))

    if not database.check_user_exist(user_id):
        user = database.User(user_id)
        await msg.answer("Привет!", reply_markup=keyboard)
        await msg.answer("Данный **неофициальный** бот создан, чтобы облегчить вашу жизнь)")
        await msg.answer("Он будет присылать новости. Например, такие:")

        post = await olimpiada.get_post(25655)
        post_keyboard = types.InlineKeyboardMarkup()
        post_keyboard.add(
            types.InlineKeyboardButton("⇩Полный текст", callback_data=full_text_cb.new(post_id=post.post_id)))
        await msg.answer(post.short_text(), reply_markup=post_keyboard)
        await msg.answer("Также вам будут приходить уведомления. Например, такое:")
        await msg.answer("Через неделю заключительный этап\n"
                         "[Всесибирская олимпиада школьников по информатике](https://olimpiada.ru/activity/316)")
        await msg.answer("‼️ Пожалуйста, настройте бота, как вам нравится, используя кнопки около клавиатуры.")
        await msg.answer("Вся информация берётся с сайта [olimpiada.ru](https://olimpiada.ru/). За "
                         "что мы приносим огромную благодарность всем людям, которые "
                         "связаны с этим замечательным сайтом!)")
    else:
        await msg.answer("Привет!", reply_markup=keyboard)
        await msg.answer("Данный неофициальный бот всё еще может помочь вам следить за олимпиадами)")


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
    except UserDeactivated or BotBlocked:
        pass
    except Exception as error:
        logging.exception(error)
        ping_admin()


async def news():
    while True:
        post_id = database.one("SELECT post_id FROM last_post")
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

        database.run("UPDATE last_post SET post_id = post_id + 1")

        text = post.short_text()
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("⇩Полный текст", callback_data=full_text_cb.new(post_id=post_id)))
        for user_id in database.news_filter(post.olimp, post.tags):
            await try_send(user_id, text=text, reply_markup=keyboard)


async def events():
    try:
        for activity_id in database.all("SELECT activity_id FROM cool_olympiads"):
            try:
                db_events = database.all("SELECT event_id FROM olympiad_events WHERE activity_id = %s", (activity_id,))
                current_events = []
                current_date = datetime.date.today()
                for event in await olimpiada.get_events(activity_id):
                    stage = database.one("SELECT stage FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
                                   (activity_id, event.event_id))
                    if stage is None:
                        database.run("INSERT INTO olympiad_events (activity_id, event_id) values (%s, %s)",
                               (activity_id, event.event_id))
                        stage = 0
                    if event.first_date is None:
                        continue

                    if stage != 1 and event.first_date - datetime.timedelta(days=1) == current_date:
                        database.run("UPDATE olympiad_events SET stage = 1 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in database.notifications_filter(activity_id):
                            activity_name = database.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через день* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    if stage != 2 and event.first_date - datetime.timedelta(days=3) == current_date:
                        database.run("UPDATE olympiad_events SET stage = 2 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in database.notifications_filter(activity_id):
                            activity_name = database.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через 3 дня* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    if stage != 3 and event.first_date - datetime.timedelta(days=7) == current_date:
                        database.run("UPDATE olympiad_events SET stage = 3 WHERE activity_id = %s AND event_id = %s",
                               (activity_id, event.event_id))
                        for user_id in database.notifications_filter(activity_id):
                            activity_name = database.one(
                                "SELECT activity_name FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
                            activity_link = f"https://olimpiada.ru/activity/{activity_id}"
                            text = f"*Через неделю* {event.event_name.lower()}\n" \
                                   f"[{activity_name}]({activity_link})"
                            await try_send(user_id, text)
                    current_events.append(event.event_id)

                for event_id in db_events:
                    if event_id not in current_events:
                        database.run("DELETE FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
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

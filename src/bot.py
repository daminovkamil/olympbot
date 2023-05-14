import requests
from aiogram import Dispatcher, Bot, types, executor
from aiogram.utils.callback_data import CallbackData
from aiogram.types import ParseMode
from aiogram.utils.exceptions import BotBlocked, UserDeactivated, BotKicked
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
        if len(post.full_text()) < 4000:
            post_keyboard.insert(
                types.InlineKeyboardButton("Показать текст", callback_data=full_text_cb.new(post_id=post.post_id)))
        post_keyboard.insert(
            types.InlineKeyboardButton("Страница новости",
                                       web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % 25655))
        )
        await msg.answer(post.short_text(), reply_markup=post_keyboard)
        await msg.answer("Также вам будут приходить уведомления. Например, такие:")
        await msg.answer("*Через 6 дней* будет пригласительный этап для 7-10 классов, точнее *в четверг 12.05.2023*.\n"
                         "\n"
                         "[Всероссийская олимпиада по математике](https://olimpiada.ru/activity/72)")
        await msg.answer("*Через 2 дня* закончится международный форум, точнее *в воскресенье 20.05.2023*.\n"
                         "\n"
                         "[Конференция «Шаг в будущее»](https://olimpiada.ru/activity/4310)")
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
        if post is None:
            await query.answer("Не получилось( Попробуйте, пожалуйста, позже")
            keyboard = types.InlineKeyboardMarkup()
            keyboard.insert(
                types.InlineKeyboardButton("Показать текст", callback_data=full_text_cb.new(post_id=post_id)))
            keyboard.insert(
                types.InlineKeyboardButton("Страница новости",
                                           web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id))
            )
            await query.message.edit_reply_markup(reply_markup=keyboard)
            return
        keyboard = types.InlineKeyboardMarkup()
        keyboard.insert(
            types.InlineKeyboardButton("Скрыть текст", callback_data=short_text_cb.new(post_id=post_id)))
        keyboard.insert(
            types.InlineKeyboardButton("Страница новости",
                                       web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id))
        )
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
        if post is None:
            await query.answer("Не получилось( Попробуйте, пожалуйста, позже")
            keyboard = types.InlineKeyboardMarkup()
            keyboard.insert(
                types.InlineKeyboardButton("Скрыть текст", callback_data=short_text_cb.new(post_id=post_id)))
            keyboard.insert(
                types.InlineKeyboardButton("Страница новости",
                                           web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id))
            )
            await query.message.edit_reply_markup(reply_markup=keyboard)
            return
        keyboard = types.InlineKeyboardMarkup()
        if len(post.full_text()) < 4000:
            keyboard.insert(
                types.InlineKeyboardButton("Показать текст", callback_data=full_text_cb.new(post_id=post_id)))
        keyboard.insert(
            types.InlineKeyboardButton("Страница новости",
                                       web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id))
        )
        await query.message.edit_text(text=post.short_text(), reply_markup=keyboard)
    except Exception as error:
        logging.exception(error)
        ping_admin()


async def try_send(*args, **kwargs):
    try:
        await bot.send_message(*args, **kwargs)
    except (BotBlocked, UserDeactivated, BotKicked):
        if "chat_id" in kwargs:
            user_id = kwargs["chat_id"]
        else:
            user_id = args[0]
        database.run("DELETE FROM users WHERE user_id = %s" % user_id)
    except Exception as error:
        logging.exception(error)


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
        if len(post.full_text()) < 4000:
            keyboard.insert(
                types.InlineKeyboardButton("Показать текст", callback_data=full_text_cb.new(post_id=post_id)))
        keyboard.insert(
            types.InlineKeyboardButton("Страница новости",
                                       web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id))
        )
        for user_id in database.news_filter(post.olimp, post.tags):
            await try_send(user_id, text=text, reply_markup=keyboard)


def get_event_stage(event: olimpiada.Event):
    today = datetime.date.today()
    if event.first_date is None:
        # 0 - не надо присылать
        # 3 - за неделю до конца
        # 4 - за три дня до конца
        # 5 - за день до конца
        # 6 - удалить событие
        days = (event.second_date - today).days
        if days <= 0:
            return 6
        if days == 1:
            return 5
        if days <= 3:
            return 4
        if days <= 7:
            return 3
        return 0
    else:
        # 0 - не надо присылать
        # 1 - за неделю до события
        # 2 - за три дня до события
        # 3 - за день до события
        # 4 - за три дня до конца события (длина события хотя бы 4 дня)
        # 5 - за день до конца
        # 6 - удалить событие
        days = (event.first_date - today).days
        if days <= 0:
            if event.second_date is None or (event.second_date - event.first_date).days < 5:
                return 6
            days = (event.second_date - today).days
            if days <= 0:
                return 6
            if days == 1:
                return 5
            if days <= 3:
                return 4
            return 3
        else:
            if days == 1:
                return 3
            if days <= 3:
                return 2
            if days <= 7:
                return 1
            return 0


def days_word(days):
    if days == 1:
        return "Завтра"
    if days % 10 == 1 and days != 11:
        return "Через %s день" % days
    if days % 10 in [2, 3, 4] and days not in [12, 13, 14]:
        return "Через %s дня" % days
    return "Через %s дней" % days


async def events():
    for event in await olimpiada.all_events():
        text = None
        today = datetime.date.today()
        activity_name = database.one("SELECT activity_name FROM cool_olympiads WHERE activity_id = %s" % event.activity_id)
        event_name = event.event_name
        event_name = event_name[0].lower() + event_name[1:]
        activity_id = event.activity_id
        if get_event_stage(event) != event.stage:
            event.stage = get_event_stage(event)
            if event.stage == 6:
                event.delete()
                continue
            else:
                event.save()
            weekdays = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
            if event.first_date is not None and event.first_date > today:
                days = (event.first_date - today).days
                weekday = weekdays[event.first_date.weekday()]
                text = f"*{days_word(days)}* будет {event_name}, " \
                       f"точнее *в {weekday} {event.first_date.strftime('%d.%m.%Y')}*.\n" \
                       f"\n" \
                       f"[{activity_name}](https://olimpiada.ru/activity/{activity_id})"
            elif event.second_date is not None and event.second_date > today:
                days = (event.second_date - today).days
                weekday = weekdays[event.second_date.weekday()]
                text = f"*{days_word(days)}* закончится {event_name}, " \
                       f"точнее *в {weekday} {event.second_date.strftime('%d.%m.%Y')}*.\n" \
                       f"\n" \
                       f"[{activity_name}](https://olimpiada.ru/activity/{activity_id})"
        if text is not None:
            for user in database.notifications_filter(event.activity_id):
                await try_send(user.user_id, text)
    await asyncio.sleep(3600)


if __name__ == "__main__":
    logging.basicConfig(filename="log", filemode="w")
    loop = asyncio.get_event_loop()
    loop.create_task(news())
    loop.create_task(events())
    loop.create_task(olimpiada.collecting_events())
    executor.start_polling(dp, skip_updates=True)

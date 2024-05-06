import datetime

from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from aiogram.types.web_app_info import WebAppInfo
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram import Bot, F

import config
import asyncio
import logging
import requests
import parsing
import sys

import botdb.events
import botdb.last_post
import botdb.connection

import sitedb.queries

import messages

from sqlalchemy import func, select

bot = Bot(token=config.bot_token, parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)

dp = Dispatcher()


class ViewFullText(CallbackData, prefix="full_text"):
    post_id: int


class ViewShortText(CallbackData, prefix="short_text"):
    post_id: int


async def try_send(*args, **kwargs):
    try:
        await bot.send_message(*args, **kwargs)
    except Exception as error:
        logging.debug(error)


async def try_delete(*args, **kwargs):
    try:
        await bot.delete_message(*args, **kwargs)
    except Exception as error:
        logging.debug(error)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    if sitedb.queries.touch_user(user_id):
        await message.answer(messages.CMD_START_NEW_USER_1_MD)
        await message.answer(messages.CMD_START_NEW_USER_2_MD)
        await message.answer(messages.CMD_START_NEW_USER_3_MD)
        post = await get_post_short_message(25655)
        await message.answer(post[0], reply_markup=post[1])
        await message.answer(messages.CMD_START_NEW_USER_4_MD)
        await message.answer(messages.CMD_START_NEW_USER_5_MD)
        await message.answer(messages.CMD_START_NEW_USER_6_MD)
        await message.answer(messages.CMD_START_NEW_USER_7_MD)
        await message.answer(messages.CMD_START_NEW_USER_8_MD)
    else:
        await message.answer(messages.CMD_START_OLD_USER_1_MD)
        await message.answer(messages.CMD_START_OLD_USER_2_MD)


@dp.error(F.update.message.as_("message"))
async def message_error_handler(event: ErrorEvent, message: Message):
    logging.critical("Critical error caused by %s", event.exception, exc_info=True)
    await message.answer(messages.ERROR_MESSAGE_MD)


@dp.error(F.update.callback_query.as_("query"))
async def query_error_handler(event: ErrorEvent, query: CallbackQuery):
    logging.critical("Critical error caused by %s", event.exception, exc_info=True)
    await query.answer(messages.ERROR_MESSAGE_PT, cache_time=20)


async def get_post_short_message(post_id):
    post = await parsing.get_post(post_id)

    if post is None:
        return None, None

    keyboard = InlineKeyboardBuilder()

    if post.text.strip() and len(post.full_text()) < 4000:
        keyboard.button(
            text=messages.BUTTON_SHOW_TEXT_PT,
            callback_data=ViewFullText(post_id=post_id)
        )

    keyboard.button(
        text=messages.BUTTON_POST_PAGE_PT,
        web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id)
    )

    keyboard.adjust(2)

    return post.short_text(), keyboard.as_markup()


async def get_post_full_message(post_id):
    post = await parsing.get_post(post_id)

    if post is None:
        return None, None

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text=messages.BUTTON_HIDE_TEXT_PT,
        callback_data=ViewShortText(post_id=post_id)
    )

    keyboard.button(
        text=messages.BUTTON_POST_PAGE_PT,
        web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id)
    )

    keyboard.adjust(2)

    return post.full_text(), keyboard.as_markup()


@dp.callback_query(ViewFullText.filter())
async def query_full_text(query: CallbackQuery, callback_data: ViewFullText):
    post_id = callback_data.post_id

    downloading_keyboard = InlineKeyboardBuilder()
    downloading_keyboard.button(text=messages.BUTTON_DOWNLOAD_PT, callback_data=ViewShortText(post_id=post_id))

    previous_markup = query.message.reply_markup

    await query.message.edit_reply_markup(reply_markup=downloading_keyboard.as_markup())

    text, markup = await get_post_full_message(post_id)

    if text is None:
        await query.answer(messages.ERROR_TRY_AGAIN_PT)
        await query.message.edit_reply_markup(reply_markup=previous_markup)
        return

    await query.message.edit_text(text=text, reply_markup=markup)


@dp.callback_query(ViewShortText.filter())
async def query_short_text(query: CallbackQuery, callback_data: ViewShortText):
    post_id = callback_data.post_id

    downloading_keyboard = InlineKeyboardBuilder()
    downloading_keyboard.button(text=messages.BUTTON_DOWNLOAD_PT, callback_data=ViewFullText(post_id=post_id))

    previous_markup = query.message.reply_markup

    await query.message.edit_reply_markup(reply_markup=downloading_keyboard.as_markup())

    text, markup = await get_post_short_message(post_id)

    if text is None:
        await query.answer(messages.ERROR_TRY_AGAIN_PT)
        await query.message.edit_reply_markup(reply_markup=previous_markup)
        return

    await query.message.edit_text(text=text, reply_markup=markup)


def ping_admin(text="Советую посмотреть логи) У кого-то что-то сломалось"):
    bot_token = config.bot_token
    chat_id = config.admin_id
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


async def news():
    while True:
        try:
            post_id = botdb.last_post.get()
            post_id += 1

            try:
                post = await parsing.get_post(post_id)
            except Exception as error:
                logging.exception(error)
                ping_admin(f"Какая-то проблема с получением новости {post_id}")
                await asyncio.sleep(3600)
                continue

            if post is None:
                async def check():
                    for delta in [1, 2, 3, 4, 5]:
                        try:
                            if await parsing.get_post(post_id + delta) is not None:
                                return True
                        finally:
                            pass
                    return False

                if await check():
                    botdb.last_post.update(post_id + 1)
                else:
                    await asyncio.sleep(3600)
                continue

            botdb.last_post.update(post_id + 1)

            text, markup = await get_post_short_message(post_id)

            for user_id in sitedb.queries.post_filter(activities=post.activities, subjects=post.subjects):
                await try_send(user_id, text=text, reply_markup=markup)
        except Exception as error:
            ping_admin("Ошибка в news()")
            ping_admin(str(error))
            logging.critical(error)
            await asyncio.sleep(3600)


async def sending_events():
    while True:
        try:
            if datetime.datetime.utcnow().hour < 7:
                await asyncio.sleep(3600)
            for event in botdb.events.current_events():
                for user_id in sitedb.queries.event_filter(event.activity_id):
                    await try_send(user_id, text=messages.event_text(event))
            botdb.events.delete_current()
        except Exception as error:
            ping_admin("Ошибка в sending_events()")
            ping_admin(str(error))
            logging.critical(error)

        await asyncio.sleep(3600 * 3)


@dp.message(Command('events'))
async def cmd_events(message: Message):
    await message.answer(messages.FUNCTION_TEMPORARILY_NOT_AVAILABLE_MD)
    # user_id = message.from_user.id
    # user = await database.users.get(user_id)
    #
    # if not user.notifications_enabled:
    #     await try_send(user_id, messages.EVENTS_TURNED_OFF_MD)
    # elif user.activities:
    #     events = list(await database.users.get_events(user))
    #     if events:
    #         await try_send(user_id, messages.EVENTS_YOURS_EVENTS_BELOW_MD)
    #         for event in events:
    #             text = await messages.event_text(event)
    #             await try_send(user_id, text=text)
    #     else:
    #         await try_send(user_id, messages.EVENTS_EMPTY_MD)
    # else:
    #     await try_send(user_id, messages.EVENTS_ACTIVITIES_NOT_CHOSEN_MD)


async def collecting_events():
    while True:
        try:
            for activity_id in sitedb.queries.activity_data.keys():
                for event in await parsing.activity_events(activity_id=activity_id):
                    event_id = event.event_id
                    db_event = botdb.events.get_event(event_id=event_id, activity_id=activity_id)
                    if db_event is None:
                        botdb.events.save_event(event)
                    else:
                        event_tup = (event.name, event.first_date, event.second_date)
                        db_event_tup = (db_event.name, db_event.first_date, db_event.second_date)
                        if event_tup != db_event_tup:
                            botdb.events.delete_event(db_event.id)
                            botdb.events.save_event(event)
                    await asyncio.sleep(60)
            await asyncio.sleep(3600 * 5)
        except Exception as error:
            ping_admin("Ошибка в collecting_events()")
            ping_admin(str(error))
            logging.critical(error)
            await asyncio.sleep(3600)


async def main() -> None:
    await asyncio.gather(
        dp.start_polling(bot),
        news(),
        sending_events(),
        collecting_events(),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    botdb.connection.create_tables()
    asyncio.run(main())

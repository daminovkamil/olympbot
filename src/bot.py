import random

from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from aiogram.types.web_app_info import WebAppInfo
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text, Bold, TextLink
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram import Bot, F

import database
import olimpiada
import config
import asyncio
import logging
import requests
import sys

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


@dp.error(F.update.message.as_("message"))
async def message_error_handler(event: ErrorEvent, message: Message):
    logging.critical("Critical error caused by %s", event.exception, exc_info=True)
    await message.answer(Text("Возникла ошибка(( Обратитесь, пожалуйста, к разработчику").as_markdown())


@dp.error(F.update.callback_query.as_("query"))
async def query_error_handler(event: ErrorEvent, query: CallbackQuery):
    logging.critical("Critical error caused by %s", event.exception, exc_info=True)
    await query.answer("Возникла ошибка(( Обратитесь, пожалуйста, к разработчику", cache_time=20)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    if not database.check_user_exist(user_id):
        database.User(user_id)
        await message.answer(
            Text("Привет!").as_markdown()
        )
        await message.answer(
            Text(
                "Данный",
                " ",
                Bold("неофициальный"),
                " ",
                "бот создан, чтобы облегчить вашу жизнь)"
            ).as_markdown()
        )
        await message.answer(
            Text("Он будет присылать новости. Например, такие:").as_markdown()
        )

        post = await olimpiada.get_post(25655)
        post_keyboard = InlineKeyboardBuilder()

        if len(post.full_text()) < 4000:
            post_keyboard.button(
                text="Показать текст",
                callback_data=ViewFullText(post_id=post.post_id)
            )

        post_keyboard.button(
            text="Страница новости",
            web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % 25655)
        )

        post_keyboard.adjust(2)

        await message.answer(post.short_text(), reply_markup=post_keyboard.as_markup())
        await message.answer(
            Text(
                "Также вам будут приходить уведомления, если вы правильно настроите бота. Например, такие:").as_markdown()
        )
        await message.answer(
            Text(
                Bold("Через 6 дней"),
                " ",
                "будет пригласительный этап для 7-10 классов, точнее",
                " ",
                Bold("в четверг 12.05.2023"),
                "\n\n",
                TextLink(
                    "Всероссийская олимпиада по математике",
                    url="https://olimpiada.ru/activity/72",
                )
            ).as_markdown()
        )
        await message.answer(
            Text(
                Bold("Через 2 дня"),
                " ",
                "закончится международный форум, точнее",
                " ",
                Bold("в воскресенье 20.05.2023"),
                "\n\n",
                TextLink(
                    "Конференция «Шаг в будущее»",
                    url="https://olimpiada.ru/activity/4310"
                )
            ).as_markdown()
        )
        await message.answer(
            Text(
                "‼️ Пожалуйста, настройте бота, как вам нравится, используя кнопку «Настройки» около клавиатуры.").as_markdown()
        )
        await message.answer(
            Text(
                "Вся информация берётся с сайта",
                " ",
                TextLink(
                    "olimpiada.ru",
                    url="https://olimpiada.ru/"
                ),
                ".",
                " ",
                "За что мы приносим огромную благодарность всем людям, которые связаны с этим замечательным сайтом!"
            ).as_markdown()
        )
    else:
        await message.answer(
            Text("Привет!").as_markdown(),
        )
        await message.answer(
            Text("Данный неофициальный бот всё еще может помочь вам следить за олимпиадами)").as_markdown()
        )


async def get_post_short_message(post_id):
    post = await olimpiada.get_post(post_id)

    if post is None:
        return None, None

    keyboard = InlineKeyboardBuilder()

    if post.text.strip() and len(post.full_text()) < 4000:
        keyboard.button(
            text="Показать текст",
            callback_data=ViewFullText(post_id=post_id)
        )

    keyboard.button(
        text="Страница новости",
        web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id)
    )

    keyboard.adjust(2)

    return post.short_text(), keyboard.as_markup()


async def get_post_full_message(post_id):
    post = await olimpiada.get_post(post_id)

    if post is None:
        return None, None

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="Скрыть текст",
        callback_data=ViewShortText(post_id=post_id)
    )

    keyboard.button(
        text="Страница новости",
        web_app=WebAppInfo(url="https://olimpiada.ru/news/%s" % post_id)
    )

    keyboard.adjust(2)

    return post.full_text(), keyboard.as_markup()


@dp.callback_query(ViewFullText.filter())
async def query_full_text(query: CallbackQuery, callback_data: ViewFullText):
    post_id = callback_data.post_id

    downloading_keyboard = InlineKeyboardBuilder()
    downloading_keyboard.button(text="Загрузка...", callback_data=ViewShortText(post_id=post_id))

    previous_markup = query.message.reply_markup

    await query.message.edit_reply_markup(reply_markup=downloading_keyboard.as_markup())

    text, markup = await get_post_full_message(post_id)

    if text is None:
        await query.answer("Не получилось( Попробуйте, пожалуйста, позже")
        await query.message.edit_reply_markup(reply_markup=previous_markup)
        return

    await query.message.edit_text(text=text, reply_markup=markup)


@dp.callback_query(ViewShortText.filter())
async def query_short_text(query: CallbackQuery, callback_data: ViewShortText):
    post_id = callback_data.post_id

    downloading_keyboard = InlineKeyboardBuilder()
    downloading_keyboard.button(text="Загрузка...", callback_data=ViewShortText(post_id=post_id))

    previous_markup = query.message.reply_markup

    await query.message.edit_reply_markup(reply_markup=downloading_keyboard.as_markup())

    text, markup = await get_post_short_message(post_id)

    if text is None:
        await query.answer("Не получилось( Попробуйте, пожалуйста, позже")
        await query.message.edit_reply_markup(reply_markup=previous_markup)
        return

    await query.message.edit_text(text=text, reply_markup=markup)


def ping_admin(text="Советую посмотреть логи) У кого-то что-то сломалось"):
    bot_token = config.bot_token
    chat_id = config.admin_id
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


async def news():
    while True:
        post_id = database.get_last_post_id()
        post_id += 1

        try:
            post = await olimpiada.get_post(post_id)
        except Exception as error:
            logging.exception(error)
            ping_admin(f"Какая-то проблема с получением новости {post_id}")
            await asyncio.sleep(3600)
            continue

        if post is None:
            async def check():
                for delta in [1, 2, 3, 4, 5]:
                    try:
                        if await olimpiada.get_post(post_id + delta) is not None:
                            return True
                    finally:
                        pass
                return False

            if await check():
                database.update_last_post_id()
            else:
                await asyncio.sleep(3600)
            continue

        database.update_last_post_id()

        text, markup = await get_post_short_message(post_id)

        for user_id in database.news_filter(post.olimp, post.tags):
            await try_send(user_id, text=text, reply_markup=markup)


async def events():
    for event in await olimpiada.all_events():
        text = None
        if event.current_stage() != event.stage:
            event.stage = event.current_stage()
            if event.stage == 6:
                event.delete()
                continue
            else:
                event.save()
            text = event.message_text()
        if text is not None:
            for user_id in database.notifications_filter(event.activity_id):
                await try_send(user_id, text)
    await asyncio.sleep(3600)


@dp.message(Command('events'))
async def showing_events(message: Message):
    user_id = message.from_user.id
    user = database.User(user_id)

    if user.olympiads:
        current_events: list[olimpiada.Event] = sorted(
            await olimpiada.user_events(user_id),
            key=lambda x: x.get_date()
        )
        if current_events:
            await try_send(user_id, Text(
                'Ниже представлены текущие события ваших избранных олимпиад'
            ).as_markdown())
            for event in current_events:
                if event.message_text is not None:
                    await try_send(user_id, event.message_text())
        else:
            await try_send(user_id, Text(
                'На данный момент нет никаких событий('
            ).as_markdown())
    else:
        await try_send(user_id, Text(
            Bold('Вы не выбрали никаких олимпиад!'),
            ' ',
            'Если вы хотите получать уведомления, то, пожалуйста, используйте кнопку «Настройки» около клавиатуры.'
        ).as_markdown()
                       )


async def main() -> None:
    await asyncio.gather(
        dp.start_polling(bot),
        news(),
        events(),
        olimpiada.collecting_events(),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

from aiogram.utils.formatting import Text, Bold, TextLink, CustomEmoji
from sitedb.queries import activity_data
from datetime import date

ERROR_MESSAGE_PT = "Возникла ошибка(( Обратитесь, пожалуйста, к разработчику"
ERROR_MESSAGE_MD = Text(ERROR_MESSAGE_PT).as_markdown()

ERROR_TRY_AGAIN_PT = "Не получилось( Попробуйте, пожалуйста, позже"

FUNCTION_TEMPORARILY_NOT_AVAILABLE_MD = Text("Функция временно не доступна((").as_markdown()

BUTTON_DOWNLOAD_PT = "Загрузка"
BUTTON_SHOW_TEXT_PT = "Показать текст"
BUTTON_HIDE_TEXT_PT = "Скрыть текст"
BUTTON_POST_PAGE_PT = "Страница новости"

CMD_START_NEW_USER_1_MD = Text("Привет!").as_markdown()
CMD_START_NEW_USER_2_MD = Text("Данный ", Bold("неофициальный"), " бот создан, чтобы облегчить вашу жизнь)").as_markdown()
CMD_START_NEW_USER_3_MD = Text("Он будет присылать новости. Например, такие:").as_markdown()
CMD_START_NEW_USER_4_MD = Text("Также вам будут приходить уведомления, если вы правильно настроите бота. Например, такие:").as_markdown()
CMD_START_NEW_USER_5_MD = Text(Bold("Через 6 дней"), " будет пригласительный этап для 7-10 классов, точнее ", Bold("в четверг 12.05.2023"), "\n\n", TextLink("Всероссийская олимпиада по математике", url="https://olimpiada.ru/activity/72")).as_markdown()
CMD_START_NEW_USER_6_MD = Text(Bold("Через 2 дня"), " закончится международный форум, точнее ", Bold("в воскресенье 20.05.2023"), "\n\n", TextLink("Конференция «Шаг в будущее»", url="https://olimpiada.ru/activity/4310")).as_markdown()
CMD_START_NEW_USER_7_MD = Text("‼️ Пожалуйста, настройте бота, как вам нравится, используя кнопку «Настройки» около клавиатуры.").as_markdown()
CMD_START_NEW_USER_8_MD = Text("Вся информация берётся с сайта ", TextLink("olimpiada.ru", url="https://olimpiada.ru/"), ". За что мы приносим огромную благодарность всем людям, которые связаны с этим замечательным сайтом!").as_markdown()

CMD_START_OLD_USER_1_MD = Text("Привет!").as_markdown()
CMD_START_OLD_USER_2_MD = Text("Данный неофициальный бот всё еще может помочь вам следить за олимпиадами)").as_markdown()

EVENTS_TURNED_OFF_MD = Text(Bold("У ваc не стоит галочка около пункта «Присылать уведомления» в настройках!"), " Если вы хотите получать уведомления, то, пожалуйста, используйте кнопку «Настройки» около клавиатуры.").as_markdown()
EVENTS_ACTIVITIES_NOT_CHOSEN_MD = Text(Bold("Вы не выбрали никаких олимпиад!"), " Если вы хотите получать уведомления, то, пожалуйста, используйте кнопку «Настройки» около клавиатуры.").as_markdown()
EVENTS_EMPTY_MD = Text("На данный момент нет никаких событий(").as_markdown()
EVENTS_YOURS_EVENTS_BELOW_MD = Text("Ниже представлены текущие события ваших избранных олимпиад").as_markdown()


async def event_text(event):
    def days_word(count):
        if count == 1:
            return "Завтра"
        if count == 0:
            return "Сегодня"
        if count % 10 == 1 and count % 100 != 11:
            return "Через %s день" % count
        if count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
            return "Через %s дня" % count
        return "Через %s дней" % count

    activity_id = event.activity_id

    event_name = event.name
    event_name = event_name[0].lower() + event_name[1:]

    activity_name = activity_data[activity_id]["name"]

    today = date.today()

    weekdays = ['в понедельник', 'во вторник', 'в среду', 'в четверг', 'в пятницу', 'в субботу', 'в воскресенье']
    weekdays_second = ['до понедельника', 'до вторника', 'до среды', 'до четверга', 'до пятницы', 'до субботы',
                       'до воскресенья']

    text = None

    if event.first_date is not None and event.first_date > today:

        if event.second_date is None:
            days = (event.first_date - today).days
            weekday = weekdays[event.first_date.weekday()]
            full_date = event.first_date.strftime("%d.%m.%Y")
            text = Text(
                "‼️ ",
                Bold(days_word(days)),
                " будет ",
                event_name,
                ", точнее ",
                Bold(
                    weekday,
                    " ",
                    full_date,
                ),
                ".\n\n",
                TextLink(activity_name, url="https://olimpiada.ru/activity/%s" % activity_id)
            ).as_markdown()
        else:
            days = (event.first_date - today).days
            weekday = weekdays[event.first_date.weekday()]
            full_date = event.first_date.strftime("%d.%m.%Y")
            text = Text(
                "‼️ ",
                Bold(days_word(days)),
                " начнется ",
                event_name,
                ", точнее ",
                Bold(
                    weekday,
                    " ",
                    full_date,
                ),
                ".\n\n",
                "Будет проводится ",
                Bold(
                    weekdays_second[event.second_date.weekday()],
                    " ",
                    event.second_date.strftime("%d.%m.%Y")
                ),
                ".\n\n",
                TextLink(activity_name, url="https://olimpiada.ru/activity/%s" % activity_id)
            ).as_markdown()

    elif event.second_date is not None and event.second_date > today:
        days = (event.second_date - today).days
        weekday = weekdays[event.second_date.weekday()]
        full_date = event.second_date.strftime('%d.%m.%Y')
        text = Text(
            "‼️ ",
            Bold(days_word(days)),
            " закончится ",
            event_name,
            ", точнее ",
            Bold(
                weekday,
                " ",
                full_date
            ),
            ".\n\n",
            TextLink(activity_name, url="https://olimpiada.ru/activity/%s" % activity_id)
        ).as_markdown()

    return text

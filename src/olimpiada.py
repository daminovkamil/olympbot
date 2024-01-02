"""Файл отвечает за запросы к сайту"""
import asyncio
import json

import requests
from bs4 import BeautifulSoup
from datetime import *
from aiogram.utils.formatting import Text, Bold, TextLink
import database
import markdownify
import logging


session = requests.Session()


class MyConverter(markdownify.MarkdownConverter):
    def escape(self, text):
        if not text:
            return ''
        return Text(text).as_markdown()


def md(html, **options):
    html = html.replace("\xa0", " ")
    return MyConverter(**options, bullets='•').convert(html)


async def get_page(url: str):
    page = session.get(url)
    if page.ok and 'ddos' not in page.text.lower():
        return page
    else:
        return None


class Post:
    """
        Определения:
        post_id: int - номер поста
        head: str - заголовок поста
        text: str - основной текст новости
        olimp: list[int] - список id прикреплённых олимпиад
        tags: list[str] - предметы, к которым относится новость
    """

    def __init__(self, post_id=0, head="", text="", olimp=None, tags=None):
        self.post_id = post_id
        self.head = head
        self.text = text
        self.olimp = olimp if olimp is not None else []
        self.tags = tags if tags is not None else []

    def short_text(self):
        result: str = f"[%s](https://olimpiada.ru/news/%s)" % (self.head, self.post_id)
        result += "\n\n"
        result += " ".join(["\#" + tag.replace(" ", "") for tag in self.tags])
        return result

    def full_text(self):
        result: str = f"[%s](https://olimpiada.ru/news/%s)" % (self.head, self.post_id)
        result += "\n\n"
        result += self.text
        result += "\n\n"
        result += " ".join(["\#" + tag.replace(" ", "") for tag in self.tags])
        return result


async def get_post(post_id: int):
    """Получаем данные с какой-то новости на сайте olimpiada.ru"""

    url = "https://olimpiada.ru/news/%s/" % post_id
    page_html = database.one("SELECT html FROM pages WHERE url = %s", (url, ))

    if page_html is None:
        page = await get_page(f"https://olimpiada.ru/news/{post_id}/")
        if page is None:
            return None
        page_html = page.text
        database.run("INSERT INTO pages (url, html) VALUES (%s, %s)", (url, page_html))

    soup = BeautifulSoup(page_html, "lxml")
    result = Post(post_id)

    left_part = soup.find("div", class_="news_left")  # часть с текстом поста
    right_part = soup.find("div", class_="news_right")  # часть с текстом прикреплённой олимпиады
    subject_tags = soup.find("div", class_="subject_tags")  # часть с тегами
    head_part = soup.find("h1", class_="headline")  # часть с заголовком

    # пытаемся добыть заголовок
    result.head = md(head_part.text)

    # пытаемся добыть основной текст
    full_text = left_part.find("div", class_="full_text")
    text_parts = []

    for elem in full_text.contents:
        if elem.name in ["p", "ul", "ol"]:
            text_parts.append(md(str(elem)).strip())
    result.text = "\n\n".join(text_parts)

    # пытаемся добыть теги
    for subject_tag in subject_tags.find_all("span", class_="subject_tag"):
        text = md(subject_tag.text[1:])
        result.tags.append(text)

    # пытаемся добыть олимпиаду, которая связанна с постом
    for olimp_for_news in right_part.find_all("div", class_="olimp_for_news"):
        href = olimp_for_news.find("a")["href"]
        activity_id = int(href[len("/activity/"):])
        activity_data = database.one("SELECT data FROM cool_olympiads WHERE activity_id = %s", (activity_id,))
        if activity_data is not None:
            activity_data = json.loads(activity_data)
            if activity_data["top_level"]:
                for child_id in activity_data["children"]:
                    result.olimp.append(child_id)
        else:
            result.olimp.append(activity_id)

    return result


class Event:
    def __init__(self, activity_id, event_id, event_name, first_date, second_date, stage):
        self.activity_id = activity_id
        self.event_id = event_id
        self.event_name = event_name
        self.first_date = first_date
        self.second_date = second_date
        self.stage = stage

    def __repr__(self):
        return f"Event #{self.activity_id}:{self.event_id} \"{self.event_name}\" from {self.first_date} to {self.second_date}"

    def __eq__(self, other):
        if other is None:
            return False
        return (self.activity_id, self.event_id, self.event_name, self.first_date, self.second_date) == (
            other.activity_id, other.event_id, other.event_name, other.first_date, other.second_date)

    def __ne__(self, other):
        return not (self == other)
    
    def get_date(self):
        today = date.today()
        if self.first_date is not None and self.first_date > today:
            return self.first_date
        elif self.second_date is not None and self.second_date > today:
            return self.second_date
        return today

    def current_stage(self):
        today = date.today()
        if self.first_date is None:
            # 0 - не надо присылать
            # 3 - за неделю до конца
            # 4 - за три дня до конца
            # 5 - за день до конца
            # 6 - удалить событие
            days = (self.second_date - today).days
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
            days = (self.first_date - today).days
            if days <= 0:
                if self.second_date is None or (self.second_date - self.first_date).days < 5:
                    return 6
                days = (self.second_date - today).days
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

    def message_text(self):
        def days_word(days):
            if days == 1:
                return "Завтра"
            if days == 0:
                return "Сегодня"
            if days % 10 == 1 and days % 100 != 11:
                return "Через %s день" % days
            if days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]:
                return "Через %s дня" % days
            return "Через %s дней" % days
        
        activity_id = self.activity_id

        event_name = self.event_name
        event_name = event_name[0].lower() + event_name[1:]

        activity_name = database.get_activity_name(activity_id)

        today = date.today()

        weekdays = ['в понедельник', 'во вторник', 'в среду', 'в четверг', 'в пятницу', 'в субботу', 'в воскресенье']
        weekdays_second = ['до понедельника', 'до вторника', 'до среды', 'до четверга', 'до пятницы', 'до субботы', 'до воскресенья']

        text = None

        if self.first_date is not None and self.first_date > today:

            if self.second_date is None:
                days = (self.first_date - today).days
                weekday = weekdays[self.first_date.weekday()]
                full_date = self.first_date.strftime("%d.%m.%Y")
                text = Text(
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
                days = (self.first_date - today).days
                weekday = weekdays[self.first_date.weekday()]
                full_date = self.first_date.strftime("%d.%m.%Y")
                text = Text(
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
                        weekdays_second[self.second_date.weekday()],
                        " ",
                        self.second_date.strftime("%d.%m.%Y")
                    ),
                    ".\n\n",
                    TextLink(activity_name, url="https://olimpiada.ru/activity/%s" % activity_id)
                ).as_markdown()

        elif self.second_date is not None and self.second_date > today:
            days = (self.second_date - today).days
            weekday = weekdays[self.second_date.weekday()]
            full_date = self.second_date.strftime('%d.%m.%Y')
            text = Text(
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

    def save(self):
        self.delete()
        database.run("INSERT INTO events (event_id, activity_id, event_name, first_date, second_date, stage) VALUES "
                     "(%s, %s, %s, %s, %s, %s)",
                     (self.event_id, self.activity_id, self.event_name, self.first_date, self.second_date, self.stage))

    def delete(self):
        database.run("DELETE FROM events WHERE event_id = %s AND activity_id = %s", (self.event_id, self.activity_id))


month_map = dict()
month_map["янв"] = 1
month_map["фев"] = 2
month_map["мар"] = 3
month_map["апр"] = 4
month_map["мая"] = 5
month_map["июн"] = 6
month_map["июл"] = 7
month_map["авг"] = 8
month_map["сен"] = 9
month_map["окт"] = 10
month_map["ноя"] = 11
month_map["дек"] = 12


async def day_and_month(day: int, month: int):
    today = date.today()
    year = today.year
    if date(year, month, day) < today:
        year += 1
    return date(year, month, day)


async def get_date(date_string: str):
    if date_string.startswith("До"):
        do, day, month = date_string.split("\xa0")
        day = int(day)
        month = month_map[month]
        return None, await day_and_month(day, month)
    if "..." not in date_string:
        day, month = date_string.split("\xa0")
        day = int(day)
        month = month_map[month]
        return await day_and_month(day, month), None
    else:
        left, right = date_string.split("...")
        day2, month2 = right.split("\xa0")
        if "\xa0" in left:
            day1, month1 = left.split("\xa0")
        else:
            day1 = int(left)
            month1 = month2
        day1 = int(day1)
        day2 = int(day2)
        month1 = month_map[month1]
        month2 = month_map[month2]
        return await day_and_month(day1, month1), await day_and_month(day2, month2)


async def activity_events(activity_id):
    page = await get_page(f"https://olimpiada.ru/activity/{activity_id}")
    if page is None:
        return []
    soup = BeautifulSoup(page.text, "lxml")
    table = soup.find("table", class_="events_for_activity")
    if table is None:
        return []
    result = []
    if table is None:
        return []
    for item in table.find_all("tr", class_="notgreyclass"):
        event_id = int(item.find("a")["href"][len(f"/activity/{activity_id}/events/"):])
        event_name = item.find("div", class_="event_name").get_text()
        date_string = item.find_all("td")[1].find("a").get_text()
        if date_string == "Отменено":
            first_date, second_date = date.today(), date.today()
        else:
            first_date, second_date = await get_date(date_string)
        event = Event(activity_id, event_id, event_name, first_date, second_date, 0)
        result.append(event)
    return result


async def all_events():
    result = []
    rows = database.all("SELECT * FROM events")
    for event_id, activity_id, event_name, first_date, second_date, stage in rows:
        result.append(Event(activity_id, event_id, event_name, first_date, second_date, stage))
    return result


async def load_event_from_db(event_id, activity_id):
    result = database.one("SELECT * FROM events WHERE event_id = %s AND activity_id = %s", (event_id, activity_id))
    if result is None:
        return None
    event_id, activity_id, event_name, first_date, second_date, stage = result
    return Event(activity_id, event_id, event_name, first_date, second_date, stage)


async def collecting_events():
    while True:
        for activity_id in database.all("SELECT activity_id FROM cool_olympiads"):
            try:
                for event in await activity_events(activity_id):
                    if event != await load_event_from_db(event.event_id, event.activity_id):
                        event.save()
                await asyncio.sleep(5)
            except Exception as error:
                logging.error(error)


async def user_events(user_id: int):
    user = database.User(user_id=user_id)

    result = []

    for activity_id in user.olympiads:
        for event_id in database.all("SELECT event_id FROM events WHERE activity_id = %s", (activity_id, )):
            result.append(await load_event_from_db(event_id, activity_id))

    return result

"""Файл отвечает за запросы к сайту"""
import asyncio

from markdownify import markdownify
from bs4 import BeautifulSoup
from datetime import *
import requests
import database
from random import randint

session = requests.Session()

def md(*args, **kwargs):
    return markdownify(*args, **kwargs).replace("\xa0", " ")


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
        text = f"[{self.head}](https://olimpiada.ru/news/{self.post_id})"
        text += "\n\n"
        text += " ".join(["#" + tag.replace(" ", "") for tag in self.tags])
        return text

    def full_text(self):
        text = f"[{self.head}](https://olimpiada.ru/news/{self.post_id})"
        text += "\n\n"
        text += self.text
        text += "\n\n"
        text += " ".join(["#" + tag.replace(" ", "") for tag in self.tags])
        return text


async def get_post(post_id: int):
    """Получаем данные с какой-то новости на сайте olimpiada.ru"""

    url = "https://olimpiada.ru/news/%s/" % post_id
    page_html = database.one("SELECT html FROM pages WHERE url = %s", (url, ))

    if page_html is None:
        page = session.get(f"https://olimpiada.ru/news/{post_id}/")
        if not page.ok:
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
    result.head = md(str(head_part), strip=['h1'])

    # пытаемся добыть основной текст
    full_text = left_part.find("div", class_="full_text")
    text_parts = []

    for elem in full_text.contents:
        if elem.name == "p" or elem.name == "ol":
            text_parts.append(markdownify(str(elem)).strip())
        if elem.name == "ul":
            text = ""
            for li in elem.find_all("li"):
                text += '• ' + markdownify(str(li), strip=['li']).strip() + "\n"
            text_parts.append(text.strip())
    result.text = "\n\n".join(text_parts)

    # пытаемся добыть теги
    for subject_tag in subject_tags.find_all("span", class_="subject_tag"):
        text = md(str(subject_tag))[1:]
        result.tags.append(text)

    # пытаемся добыть олимпиаду, которая связанна с постом
    for olimp_for_news in right_part.find_all("div", class_="olimp_for_news"):
        href = olimp_for_news.find("a")["href"]
        activity_id = int(href[len("/activity/"):])
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
        return (self.activity_id, self.event_id, self.event_name, self.first_date, self.second_date) == (
            other.activity_id, other.event_id, other.event_name, other.first_date, other.second_date)

    def __ne__(self, other):
        return not (self == other)

    def save(self):
        database.run("DELETE FROM events WHERE event_id = %s AND activity_id = %s", (self.event_id, self.activity_id))
        database.run("INSERT INTO events (event_id, activity_id, event_name, first_date, second_date, stage) VALUES "
                     "(%s, %s, %s, %s, %s, %s)",
                     (self.event_id, self.activity_id, self.event_name, self.first_date, self.second_date, self.stage))


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
    page = session.get(f"https://olimpiada.ru/activity/{activity_id}")
    if not page.ok:
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
        event = Event(activity_id, event_id, event_name, first_date, second_date)
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
            for event in await activity_events(activity_id):
                if event != await load_event_from_db(event.event_id, event.activity_id):
                    event.save()
            await asyncio.sleep(60)

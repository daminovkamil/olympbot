"""Файл отвечает за запросы к сайту"""
import requests
from bs4 import BeautifulSoup
import datetime
from aiogram.utils.formatting import Text, Bold
import markdownify

from typing import Set
from dataclasses import dataclass, field

import botdb.pages
import botdb.events
import sitedb.queries
import logging

request_session = requests.Session()


class MyConverter(markdownify.MarkdownConverter):
    def escape(self, text):
        if not text.strip():
            return ''
        return Text(text).as_markdown()

    def convert_a(self, el, text, convert_as_inline):
        prefix, suffix, text = markdownify.chomp(text)
        if not text:
            return ''
        href = el.get('href')
        if href and href[0] == '/':
            href = 'https://olimpiada.ru' + href
        title = el.get('title')
        if (self.options['autolinks']
                and text.replace(r'\_', '_') == href
                and not title
                and not self.options['default_title']):
            return '<%s>' % href
        if self.options['default_title'] and not title:
            title = href
        title_part = ' "%s"' % title.replace('"', r'\"') if title else ''
        return '%s[%s](%s%s)%s' % (prefix, text, href, title_part, suffix) if href else text

    def convert_hn(self, *args, **kwargs):
        return ''

    def convert_hr(self, *args, **kwargs):
        return ''

    def convert_li(self, el, text, convert_as_inline):
        parent = el.parent
        if parent is not None and parent.name == 'ol':
            if parent.get("start"):
                start = int(parent.get("start"))
            else:
                start = 1
            bullet = '*%s\.*' % (start + parent.index(el))
        else:
            depth = -1
            while el:
                if el.name == 'ul':
                    depth += 1
                el = el.parent
            bullets = self.options['bullets']
            bullet = bullets[depth % len(bullets)]
        return '%s %s\n' % (bullet, (text or '').strip())

    def convert_img(self, el, text, convert_as_inline):
        alt = el.attrs.get('alt', None) or 'Изображение'
        src = el.attrs.get('src', None) or ''
        title = el.attrs.get('title', None) or ''
        title_part = ' "%s"' % title.replace('"', r'\"') if title else ''
        if (convert_as_inline
                and el.parent.name not in self.options['keep_inline_images_in']):
            return alt

        return '[%s](%s%s)' % (alt, src, title_part)

    def convert_table(self, *args, **kwargs):
        return Bold('В данном месте должна быть таблица, но показ таблиц не поддерживается. '
                    'Для просмотра таблицы, перейдите на страницу данного поста.\n\n').as_markdown()

    def convert_td(self, *args, **kwargs):
        return ''

    def convert_th(self, *args, **kwargs):
        return ''

    def convert_tr(self, *args, **kwargs):
        return ''


def md(html, **options):
    html = html.replace("\xa0", " ")
    return MyConverter(**options, bullets=['•', '‣', '•']).convert(html)


async def get_page(url: str):
    global request_session
    four_days_ago = datetime.datetime.now() - datetime.timedelta(days=4)

    result = botdb.pages.get_page(url)

    if result is not None:
        page, loaded = result
        if page is not None and loaded < four_days_ago:
            botdb.pages.delete_page(url)
            page = None
    else:
        page = None

    if page is not None:
        return page

    try:
        page = request_session.get(url)

        if page.ok:
            if 'ddos' not in page.text.lower():
                botdb.pages.add_page(url, page.text)
                return page.text
            else:
                logging.info("DDoS protection detected!")
        return None
    except Exception as error:
        logging.error(error)
        request_session = requests.Session()
        return None


@dataclass
class Post:
    id: int
    title: str
    text: str
    activities: Set[int] = field(default_factory=set)
    subjects: Set[int] = field(default_factory=set)

    def short_text(self):
        return "[%s](https://olimpiada.ru/news/%s)" % (self.title, self.id)

    def full_text(self):
        result = "*%s*" % self.title

        if self.text.strip():
            result += "\n\n"
            result += self.text.strip()

        if self.subjects:
            result += "\n\n"
            for subject_id in self.subjects:
                subject_name = sitedb.queries.subject_name_by_id[subject_id]
                result += Text("#%s " % subject_name.replace(" ", "")).as_markdown()

        return result.strip()


async def get_post(post_id: int):
    """Получаем данные с какой-то новости на сайте olimpiada.ru"""

    url = "https://olimpiada.ru/news/%s/" % post_id
    page_html = await get_page(url)
    if page_html is None:
        return None

    soup = BeautifulSoup(page_html, "lxml")

    left_part = soup.find("div", class_="news_left")  # часть с текстом поста
    right_part = soup.find("div", class_="news_right")  # часть с текстом прикреплённой олимпиады
    subject_tags = soup.find("div", class_="subject_tags")  # часть с тегами
    head_part = soup.find("h1", class_="headline")  # часть с заголовком

    # пытаемся добыть заголовок
    title = md(head_part.text)

    # пытаемся добыть основной текст
    full_text = left_part.find("div", class_="full_text")
    text = md(str(full_text))

    # пытаемся добыть теги
    subjects: Set[int] = set()
    for subject_tag in subject_tags.find_all("span", class_="subject_tag"):
        name = md(subject_tag.text[1:])
        try:
            subjects.add(sitedb.queries.subjects_id_by_name[name])
        except Exception as error:
            logging.error(error)

    # пытаемся добыть олимпиаду, которая связанна с постом
    activities: Set[int] = set()
    activity_data = sitedb.queries.activity_data

    for olimp_for_news in right_part.find_all("div", class_="olimp_for_news"):
        href = olimp_for_news.find("a")["href"]
        activity_id = int(href[len("/activity/"):])
        if activity_id in activity_data:
            data = activity_data[activity_id]
            if "top_level" in data and data["top_level"]:
                if "children" in data:
                    for child_id in data["children"]:
                        activities.add(child_id)
            else:
                activities.add(activity_id)

    return Post(post_id, title, text, activities, subjects)


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
    today = datetime.date.today()
    year = today.year
    if datetime.date(year, month, day) < today:
        year += 1
    return datetime.date(year, month, day)


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
    url = f"https://olimpiada.ru/activity/{activity_id}"
    page = await get_page(url)
    if page is None:
        return []
    soup = BeautifulSoup(page, "lxml")
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
            first_date, second_date = datetime.date.today(), datetime.date.today()
        else:
            first_date, second_date = await get_date(date_string)
        event = botdb.events.Event(
            event_id=event_id,
            activity_id=activity_id,
            name=event_name,
            first_date=first_date,
            second_date=second_date
        )
        result.append(event)
    return result

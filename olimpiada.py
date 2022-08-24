"""Файл отвечает за запросы к сайту"""
from markdownify import markdownify
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize
import requests


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
        text += sent_tokenize(self.text)[0]
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

    page = requests.get(f"https://olimpiada.ru/news/{post_id}/")

    if not page.ok:
        return None

    soup = BeautifulSoup(page.text, "lxml")
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
                text += '◾ ' + markdownify(str(li), strip=['li']).strip() + "\n"
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

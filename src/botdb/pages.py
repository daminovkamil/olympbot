from .connection import db


def get_page(url: str):
    cursor = db.cursor()
    cursor.execute(
        "SELECT html, loaded FROM pages WHERE url = ?", (url,)
    )
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result


def add_page(url: str, html: str):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO pages (url, html) VALUES (?, ?)", (url, html)
    )
    db.commit()


def delete_page(url: str):
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM pages WHERE url = ?", (url,)
    )
    db.commit()

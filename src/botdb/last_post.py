from .connection import db
from typing import Optional


def get() -> Optional[int]:
    cursor = db.cursor()
    cursor.execute("SELECT post_id FROM last_post WHERE 1")
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result[0]


def update(post_id: int) -> None:
    cursor = db.cursor()
    cursor.execute("UPDATE last_post SET post_id = ? WHERE 1", (post_id, ))
    db.commit()


def put(post_id: int) -> None:
    cursor = db.cursor()
    cursor.execute("DELETE FROM last_post WHERE 1")
    cursor.execute("INSERT INTO last_post VALUES (?)", (post_id,))
    db.commit()

import sqlite3
import pathlib

BASE = pathlib.Path(__file__).parent

db = sqlite3.connect(BASE / "bot.db", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


def create_tables():
    cursor = db.cursor()
    with open(BASE / "creating_tables.sql", "r") as file:
        cursor.executescript(file.read())
        db.commit()

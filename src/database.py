from __future__ import annotations

import json
from mysql.connector import connect
from config import database_data


def run(*args):
    with connect(**database_data) as connection:
        with connection.cursor() as cursor:
            cursor.execute(*args)
            connection.commit()


def one(*args):
    with connect(**database_data) as connection:
        with connection.cursor() as cursor:
            cursor.execute(*args)
            res: tuple | None = cursor.fetchone()
            if res is not None and len(res) == 1:
                return res[0]
            else:
                return res


def all(*args):
    with connect(**database_data) as connection:
        with connection.cursor() as cursor:
            cursor.execute(*args)
            res = cursor.fetchall()
            if len(res) != 0 and len(res[0]) == 1:
                res = [item[0] for item in res]
            return res


class User:
    def __init__(self, user_id, data=None, settings=None):
        self.user_id = user_id
        if data is None and one("SELECT COUNT(*) FROM users WHERE user_id = %s" % user_id):
            data, settings = one("SELECT data, settings FROM users WHERE user_id = %s", (user_id, ))
        if data is None:
            data = json.dumps({
                "subjects": [],
                "olympiads": []
            })
            settings = json.dumps({
                "subjects_filter": False,
                "olympiads_filter": False,
                "notifications_enabled": False,
                "news_enabled": True
            })

            run("INSERT INTO users (user_id, data, settings) VALUES (%s, %s, %s)", (user_id, data, settings))

            self.subjects = []
            self.olympiads = []

            self.subjects_filter = False
            self.olympiads_filter = False
            self.notifications_enabled = False
            self.news_enabled = True
        else:
            data = json.loads(data)
            settings = json.loads(settings)

            self.subjects = data["subjects"]
            self.olympiads = data["olympiads"]

            self.subjects_filter = settings["subjects_filter"]
            self.olympiads_filter = settings["olympiads_filter"]
            self.notifications_enabled = settings["notifications_enabled"]
            self.news_enabled = settings["news_enabled"]

        self.olympiads = [str(olympiad) for olympiad in self.olympiads]

    def save(self):
        data = json.dumps({
            "subjects": self.subjects,
            "olympiads": self.olympiads
        }, ensure_ascii=False)
        settings = json.dumps({
            "subjects_filter": self.subjects_filter,
            "olympiads_filter": self.olympiads_filter,
            "notifications_enabled": self.notifications_enabled,
            "news_enabled": self.news_enabled
        }, ensure_ascii=False)
        run("UPDATE users SET data = '%s' WHERE user_id = %s" % (data, self.user_id))
        run("UPDATE users SET settings = '%s' WHERE user_id = %s" % (settings, self.user_id))


def get_users_list():
    users = []
    for user_id, data, settings in all("SELECT user_id, data, settings FROM users"):
        users.append(User(user_id, data, settings))
    return users


def notifications_filter(olympiad):
    olympiad = str(olympiad)
    result = []
    for user in get_users_list():
        if user.notifications_enabled and olympiad in user.olympiads:
            result.append(user.user_id)
    return result


def news_filter(olympiads, subjects):
    result = []
    olympiads = set([str(item) for item in olympiads])
    subjects = set(subjects)
    for user in get_users_list():
        first_condition = user.news_enabled
        second_condition = not user.olympiads_filter or len(olympiads) == 0 or len(olympiads & set(user.olympiads)) != 0
        third_condition = not user.subjects_filter or len(subjects) == 0 or len(subjects & set(user.subjects)) != 0
        if first_condition and second_condition and third_condition:
            result.append(user.user_id)
    return result


def check_user_exist(user_id: int):
    return one("SELECT user_id FROM users WHERE user_id = %s" % user_id) is not None


def get_activity_name(activity_id: int):
    return one("SELECT activity_name FROM cool_olympiads WHERE activity_id = %s" % activity_id)


def get_last_post_id():
    return one("SELECT post_id FROM last_post")


def update_last_post_id():
    run("UPDATE last_post SET post_id = post_id + 1")

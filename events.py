import database
import olimpiada
import requests
import config
import logging
import asyncio

logging.basicConfig(filename="logs/events.log", filemode="a")
loop = asyncio.get_event_loop()
run = loop.run_until_complete


def ping_admin():
    bot_token = config.bot_token
    chat_id = config.admin_id
    text = "Советую посмотреть логи) Ошибка в event.py"
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


while True:
    try:
        for activity_id in run(database.fetch("SELECT activity_id FROM cool_olympiads")):
            for event in run(olimpiada.get_events(activity_id)):
                if run(database.fetchrow(
                        "SELECT activity_id FROM olympiad_events WHERE activity_id = %s AND event_id = %s",
                        (activity_id, event.event_id))) is None:
                    run(database.execute(
                        "INSERT INTO olympiad_events (activity_id, event_id, event_name, first_date, second_date) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (event.activity_id, event.event_id, event.event_name, event.first_date, event.second_date)))
        run(database.execute("DELETE FROM olympiad_events WHERE (second_date IS NOT NULL AND "
                             "second_date < CURRENT_DATE) OR (second_date IS NULL AND first_date < CURRENT_DATE)"))
    except Exception as error:
        logging.exception(error)
        ping_admin()

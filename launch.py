from os import system

import config
import requests


def ping_admin():
    bot_token = config.bot_token
    chat_id = config.admin_id
    text = "Бот опять упал("
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


while True:
    system("python3 bot.py > output.txt")
    system("cp output.txt saved.txt")
    ping_admin()

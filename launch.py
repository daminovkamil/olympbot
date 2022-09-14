from os import system

import config
import requests


def ping_admin():
    bot_token = config.bot_token
    chat_id = config.admin_id
    text = "Бот опять упал("
    requests.get(f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={text}")


def send_files():
    bot_token = config.bot_token
    chat_id = config.admin_id
    system(f"curl -s -v -F \"chat_id={chat_id}\" -F document=@./output/bot.out https://api.telegram.org/bot{bot_token}/sendDocument")
    system(f"curl -s -v -F \"chat_id={chat_id}\" -F document=@./output/bot.err https://api.telegram.org/bot{bot_token}/sendDocument")
    system(f"curl -s -v -F \"chat_id={chat_id}\" -F document=@./output/bot.log https://api.telegram.org/bot{bot_token}/sendDocument")


while True:
    system("python3 bot.py > output/bot.out 2> output/bot.err")
    ping_admin()
    send_files()

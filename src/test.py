import requests
import database
import config
session = requests.Session()

url = "https://api.telegram.org/bot1801938752:AAFZgJR00Lxcygf0Z3tmhDR_ZQcCpnWTxMY/forwardMessage?chat_id=%s&from_chat_id=-1001660439879&message_id=20&disable_notification=false"
requests.get(url % config.admin_id)
input()
for user_id in database.all("SELECT user_id FROM users"):
    requests.get(url % user_id)

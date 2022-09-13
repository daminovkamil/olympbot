#!/bin/sh

bot_token="1902465468:AAHONMuPinzkDk-a6OyAoWZ7pmIMLLxCAng"
admin_id=701798856
text="Есть какая-то проблема в файле events.py("

out="./output/events.out"
err="./output/events.err"
log="./output/events.log"

mkdir -p output

if [ ! -f out]
then
  touch out
fi

if [ ! -f log]
then
  touch log
fi

if [ ! -f err]
then
  touch err
fi

while true
do
  python3 events.py > ${out} 2> ${err}
  curl -s \
      -X POST \
      https://api.telegram.org/bot$bot_token/sendMessage \
      -d text="$text" \
      -d chat_id=$admin_id
  curl -F document=@${out} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
  curl -F document=@${err} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
  curl -F document=@${log} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
done

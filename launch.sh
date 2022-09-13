#!/bin/sh

bot_token="1801938752:AAFZgJR00Lxcygf0Z3tmhDR_ZQcCpnWTxMY"
admin_id=701798856
text="Бот упал("

out="./output/bot.out"
err="./output/bot.err"
log="./output/bot.log"

mkdir -p output

if [ ! -f $out];
then
  touch $out
fi

if [ ! -f $log];
then
  touch $log
fi

if [ ! -f $err];
then
  touch $err
fi

while true
do
  python3 bot.py > ${out} 2> ${err}
  curl -s \
      -X POST \
      https://api.telegram.org/bot$bot_token/sendMessage \
      -d text="$text" \
      -d chat_id=$admin_id
  curl -F document=@${out} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
  curl -F document=@${err} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
  curl -F document=@${log} https://api.telegram.org/bot${bot_token}/sendDocument?chat_id=${admin_id}
done

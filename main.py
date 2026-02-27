import os
import telebot

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Bot ishlayapti ✅")

@bot.message_handler(content_types=["text"])
def echo(m):
    bot.reply_to(m, m.text)

bot.infinity_polling()

import telebot
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bot aktif Orhan usta 👑")

bot.infinity_polling()

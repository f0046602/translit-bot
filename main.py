import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot

TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    raise RuntimeError("TOKEN topilmadi!")

bot = telebot.TeleBot(TOKEN)

# Render uchun port ochamiz
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Bot ishlayapti ✅")

@bot.message_handler(func=lambda m: True)
def echo(m):
    bot.reply_to(m, m.text)

bot.infinity_polling()

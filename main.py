import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- simple HTTP server for Render health check ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# Start tiny web server in background
threading.Thread(target=run_web, daemon=True).start()

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Bot ishlayapti ✅ Matn yuboring: lotin/kirill o‘giraman.")

@bot.message_handler(content_types=["text"])
def echo(m):
    bot.reply_to(m, m.text)

bot.infinity_polling()

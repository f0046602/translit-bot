import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from telebot import types

from local_translator import LocalTranslator

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
translator = LocalTranslator()

# ✅ Chapdagi "/" komandalar menyusi
bot.set_my_commands([
    types.BotCommand("start", "Botni ishga tushirish"),
    types.BotCommand("menu", "Menyu"),
    types.BotCommand("translit", "Translit rejimi"),
    types.BotCommand("tarjima", "Tarjima rejimi"),
    types.BotCommand("help", "Yordam"),
])

# ---------------- Health server (Railway/Render) ----------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ---------------- Apostrof normalizatsiya ----------------
def normalize_apostrophe(s: str) -> str:
    return (s.replace("`", "’")
             .replace("'", "’")
             .replace("ʻ", "’")
             .replace("ʼ", "’")
             .replace("‘", "’")
             .replace("´", "’"))

# ---------------- Translit (Lotin <-> Kirill) ----------------
LAT_MULTI = {
    "sh": "ш", "ch": "ч", "yo": "ё", "yu": "ю", "ya": "я", "ng": "нг",
    "Sh": "Ш", "Ch": "Ч", "Yo": "Ё", "Yu": "Ю", "Ya": "Я", "Ng": "Нг",
    "o’": "ў", "g’": "ғ", "O’": "Ў", "G’": "Ғ",
    "oʻ": "ў", "gʻ": "ғ", "Oʻ": "Ў", "Gʻ": "Ғ",
    "o‘": "ў", "g‘": "ғ", "O‘": "Ў", "G‘": "Ғ",
}
LAT1 = {
    "a":"а","b":"б","v":"в","g":"г","d":"д","e":"е","j":"ж","z":"з","i":"и","y":"й","k":"к","l":"л",
    "m":"м","n":"н","o":"о","p":"п","r":"р","s":"с","t":"т","u":"у","f":"ф","x":"х","q":"қ","h":"ҳ",
    "A":"А","B":"Б","V":"В","G":"Г","D":"Д","E":"Е","J":"Ж","Z":"З","I":"И","Y":"Й","K":"К","L":"Л",
    "M":"М","N":"Н","O":"О","P":"П","R":"Р","S":"С","T":"Т","U":"У","F":"Ф","X":"Х","Q":"Қ","H":"Ҳ",
    "’":"’"
}
CYR2 = {
    "ш":"sh","ч":"ch","ё":"yo","ю":"yu","я":"ya",
    "Ш":"Sh","Ч":"Ch","Ё":"Yo","Ю":"Yu","Я":"Ya",
    "ў":"o‘","ғ":"g‘","қ":"q","ҳ":"h",
    "Ў":"O‘","Ғ":"G‘","Қ":"Q","Ҳ":"H"
}
CYR1 = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ж":"j","з":"z","и":"i","й":"y","к":"k","л":"l",
    "м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"x","ц":"ts","э":"e",
    "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ж":"J","З":"Z","И":"I","Й":"Y","К":"K","Л":"L",
    "М":"M","Н":"N","О":"O","П":"P","Р":"R","С":"S","Т":"T","У":"U","Ф":"F","Х":"X","Ц":"Ts","Э":"E",
    "ь":"", "ъ":"", "Ь":"", "Ъ":""
}

def is_cyrillic_text(s: str) -> bool:
    for ch in s:
        if ("А" <= ch <= "я") or ch in "ЎўҒғҚқҲҳЁё":
            return True
    return False

def cyr_to_lat(s: str) -> str:
    return "".join(CYR2.get(ch, CYR1.get(ch, ch)) for ch in s)

def lat_to_cyr(s: str) -> str:
    s = normalize_apostrophe(s)
    out = []
    i = 0
    while i < len(s):
        if i + 2 <= len(s):
            two = s[i:i+2]
            if two in LAT_MULTI:
                out.append(LAT_MULTI[two])
                i += 2
                continue
        out.append(LAT1.get(s[i], s[i]))
        i += 1
    return "".join(out)

# ---------------- State & Menus ----------------
USER = {}  # uid -> {"mode": "translit"/"translate", "route": ("uz","ru")}

ROUTES_TEXT = {
    "🇺🇿 UZ ➜ 🇷🇺 RU": ("uz", "ru"),
    "🇷🇺 RU ➜ 🇺🇿 UZ": ("ru", "uz"),
    "🇺🇿 UZ ➜ 🇬🇧 EN": ("uz", "en"),
    "🇬🇧 EN ➜ 🇺🇿 UZ": ("en", "uz"),
    "🇷🇺 RU ➜ 🇬🇧 EN": ("ru", "en"),
    "🇬🇧 EN ➜ 🇷🇺 RU": ("en", "ru"),
}

MAIN_BTNS = {"🏠 Start", "🔁 Translit", "🌍 Tarjima", "ℹ️ Yordam", "⬅️ Orqaga"} | set(ROUTES_TEXT.keys())

def state(uid: int):
    if uid not in USER:
        USER[uid] = {"mode": "translit", "route": ("uz", "ru")}
    return USER[uid]

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏠 Start", "🔁 Translit")
    kb.row("🌍 Tarjima", "ℹ️ Yordam")
    return kb

def routes_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🇺🇿 UZ ➜ 🇷🇺 RU", "🇷🇺 RU ➜ 🇺🇿 UZ")
    kb.row("🇺🇿 UZ ➜ 🇬🇧 EN", "🇬🇧 EN ➜ 🇺🇿 UZ")
    kb.row("🇷🇺 RU ➜ 🇬🇧 EN", "🇬🇧 EN ➜ 🇷🇺 RU")
    kb.row("⬅️ Orqaga")
    return kb

def pretty_route(r):
    return f"{r[0].upper()} ➜ {r[1].upper()}"

def send(chat_id: int, text: str):
    # ✅ har safar menu chiqib turadi
    bot.send_message(chat_id, text, reply_markup=main_menu())

# ---------------- Commands ----------------
@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    st = state(m.from_user.id)
    # ✅ MUHIM: start bosilganda doim translitga qaytadi
    st["mode"] = "translit"

    send(
        m.chat.id,
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "🔁 <b>Translit</b> — Kiril ↔ Lotin avtomatik.\n"
        "🌍 <b>Tarjima</b> — faqat UZ/RU/EN.\n\n"
        f"📌 <b>Hozirgi rejim:</b> 🔁 Translit\n"
        f"🔀 <b>Tarjima yo‘nalishi:</b> {pretty_route(st['route'])}\n\n"
        "👇 Pastdagi tugmalardan tanlang:"
    )

@bot.message_handler(commands=["translit"])
def cmd_translit(m):
    st = state(m.from_user.id)
    st["mode"] = "translit"
    send(m.chat.id, "✅ <b>Translit</b> rejimi yoqildi.\nMatn yuboring.")

@bot.message_handler(commands=["tarjima"])
def cmd_translate(m):
    st = state(m.from_user.id)
    st["mode"] = "translate"
    bot.send_message(m.chat.id, "🌍 <b>Tarjima</b>\nYo‘nalishni tanlang:", reply_markup=routes_menu())

@bot.message_handler(commands=["help"])
def cmd_help(m):
    send(
        m.chat.id,
        "ℹ️ <b>Yordam</b>\n\n"
        "🔁 Translit: matn yuborsangiz avtomatik Kiril ↔ Lotin qiladi.\n"
        "🌍 Tarjima: yo‘nalish tanlaysiz, keyin matn yuborasiz.\n\n"
        "Komandalar: /start /menu /translit /tarjima /help"
    )

# ---------------- Buttons ----------------
@bot.message_handler(func=lambda m: (m.text or "") == "🏠 Start")
def btn_start(m):
    cmd_start(m)

@bot.message_handler(func=lambda m: (m.text or "") == "🔁 Translit")
def btn_translit(m):
    cmd_translit(m)

@bot.message_handler(func=lambda m: (m.text or "") == "🌍 Tarjima")
def btn_translate(m):
    cmd_translate(m)

@bot.message_handler(func=lambda m: (m.text or "") == "ℹ️ Yordam")
def btn_help(m):
    cmd_help(m)

@bot.message_handler(func=lambda m: (m.text or "") == "⬅️ Orqaga")
def btn_back(m):
    send(m.chat.id, "🏠 Menu:")

@bot.message_handler(func=lambda m: (m.text or "") in ROUTES_TEXT)
def pick_route(m):
    st = state(m.from_user.id)
    st["mode"] = "translate"
    st["route"] = ROUTES_TEXT[m.text]
    send(m.chat.id, f"✅ Tanlandi: <b>{m.text}</b>\nEndi matn yuboring — tarjima qilib beraman.")

# ---------------- Text handler ----------------
@bot.message_handler(content_types=["text"])
def on_text(m):
    txt = (m.text or "").strip()
    if not txt:
        return

    # Menyu tugmalarini bu handler qayta ishlamasin
    if txt in MAIN_BTNS:
        return

    st = state(m.from_user.id)

    if st["mode"] == "translate":
        src, dst = st["route"]
        try:
            out = translator.translate(txt, src=src, dst=dst)
            send(m.chat.id, out)
        except Exception:
            send(m.chat.id, "❌ Tarjima xatolik berdi. 🌍 Tarjima tugmasidan yo‘nalishni qayta tanlang.")
        return

    # Default: translit
    txt_norm = normalize_apostrophe(txt)
    if is_cyrillic_text(txt_norm):
        send(m.chat.id, cyr_to_lat(txt_norm))
    else:
        send(m.chat.id, lat_to_cyr(txt_norm))

bot.infinity_polling(skip_pending=True)

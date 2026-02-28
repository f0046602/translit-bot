import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from telebot import types
from googletrans import Translator

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
translator = Translator()

# ---------------- Render uchun HTTP server ----------------
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
    out = []
    for ch in s:
        out.append(CYR2.get(ch, CYR1.get(ch, ch)))
    return "".join(out)

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

# ---------------- UI / State ----------------
# Har user uchun: {"mode": "translit"/"translate", "route": ("uz","ru")}
USER = {}

ROUTES = [
    ("UZB ➜ RUS", ("uz", "ru"), "tr_uz_ru"),
    ("RUS ➜ UZB", ("ru", "uz"), "tr_ru_uz"),
    ("UZB ➜ ENG", ("uz", "en"), "tr_uz_en"),
    ("ENG ➜ UZB", ("en", "uz"), "tr_en_uz"),
    ("RUS ➜ ENG", ("ru", "en"), "tr_ru_en"),
    ("ENG ➜ RUS", ("en", "ru"), "tr_en_ru"),
]
ROUTE_BY_CB = {cb: route for _, route, cb in ROUTES}
ROUTE_NAME_BY_CB = {cb: name for name, _, cb in ROUTES}

def get_user_state(uid: int):
    if uid not in USER:
        USER[uid] = {"mode": "translit", "route": ("uz", "ru")}
    return USER[uid]

def main_menu_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔁 Translit (Kiril ↔ Lotin)", callback_data="mode_translit"),
        types.InlineKeyboardButton("🌍 Tarjima (UZ/RU/EN)", callback_data="mode_translate"),
    )
    kb.add(types.InlineKeyboardButton("ℹ️ Yordam", callback_data="help"))
    return kb

def translate_routes_kb(current_cb: str | None = None):
    kb = types.InlineKeyboardMarkup(row_width=2)
    for name, _, cb in ROUTES:
        label = f"✅ {name}" if cb == current_cb else name
        kb.add(types.InlineKeyboardButton(label, callback_data=cb))
    kb.add(types.InlineKeyboardButton("⬅️ Menyu", callback_data="back_menu"))
    return kb

def pretty_route(route: tuple[str, str]) -> str:
    return f"{route[0].upper()} ➜ {route[1].upper()}"

def send_menu(chat_id: int, uid: int, edit_message=None):
    st = get_user_state(uid)
    text = (
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "Quyidagilardan birini tanlang:\n"
        "🔁 <b>Translit</b> — Kiril ↔ Lotin avtomatik.\n"
        "🌍 <b>Tarjima</b> — faqat UZB/RUS/ENG orasida.\n\n"
        f"📌 <b>Hozirgi rejim:</b> {('🔁 Translit' if st['mode']=='translit' else '🌍 Tarjima')}\n"
        f"🔀 <b>Tarjima yo‘nalishi:</b> {pretty_route(st['route'])}"
    )
    if edit_message:
        bot.edit_message_text(text, chat_id, edit_message.message_id, reply_markup=main_menu_kb())
    else:
        bot.send_message(chat_id, text, reply_markup=main_menu_kb())

# ---------------- Commands ----------------
@bot.message_handler(commands=["start", "menu"])
def start(m):
    send_menu(m.chat.id, m.from_user.id)

# ---------------- Callbacks ----------------
@bot.callback_query_handler(func=lambda c: c.data in ["mode_translit", "mode_translate", "help", "back_menu"])
def handle_main_callbacks(c):
    uid = c.from_user.id
    st = get_user_state(uid)

    if c.data == "mode_translit":
        st["mode"] = "translit"
        bot.answer_callback_query(c.id, "Translit rejimi yoqildi ✅")
        send_menu(c.message.chat.id, uid, edit_message=c.message)

    elif c.data == "mode_translate":
        st["mode"] = "translate"
        # route tanlash sahifasi
        # current route cb ni topamiz
        current_cb = None
        for name, route, cb in ROUTES:
            if route == st["route"]:
                current_cb = cb
                break
        bot.answer_callback_query(c.id, "Tarjima rejimi ✅ Yo‘nalishni tanlang")
        bot.edit_message_text(
            "🌍 <b>Tarjima</b>\n\nYo‘nalishni tanlang (UZB/RUS/ENG):",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=translate_routes_kb(current_cb)
        )

    elif c.data == "back_menu":
        bot.answer_callback_query(c.id)
        send_menu(c.message.chat.id, uid, edit_message=c.message)

    elif c.data == "help":
        bot.answer_callback_query(c.id)
        text = (
            "ℹ️ <b>Yordam</b>\n\n"
            "✅ <b>Translit</b> rejimida: matn yuborsangiz, Kiril ↔ Lotin avtomatik o‘giriladi.\n\n"
            "✅ <b>Tarjima</b> rejimida: yo‘nalishni tanlaysiz (UZ/RU/EN), keyin matn yuborsangiz tarjima qilib beradi.\n\n"
            "⚙️ Menyuni chaqirish: /menu"
        )
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=main_menu_kb())

@bot.callback_query_handler(func=lambda c: c.data in ROUTE_BY_CB)
def handle_route_pick(c):
    uid = c.from_user.id
    st = get_user_state(uid)
    st["mode"] = "translate"
    st["route"] = ROUTE_BY_CB[c.data]

    # current cb uchun belgi qo'yamiz
    bot.answer_callback_query(c.id, f"Tanlandi: {ROUTE_NAME_BY_CB[c.data]} ✅")
    bot.edit_message_text(
        f"🌍 <b>Tarjima rejimi yoqildi</b>\n\n"
        f"🔀 <b>Yo‘nalish:</b> {ROUTE_NAME_BY_CB[c.data]}\n\n"
        "Endi matn yuboring — men tarjima qilib beraman.",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=translate_routes_kb(current_cb=c.data)
    )

# ---------------- Text handler ----------------
@bot.message_handler(content_types=["text"])
def on_text(m):
    uid = m.from_user.id
    st = get_user_state(uid)

    txt = (m.text or "").strip()
    if not txt:
        return

    # Buyruqlar bo'lsa ham (masalan /menu) bu handlerga tushib qolmasin:
    if txt.startswith("/"):
        return

    if st["mode"] == "translate":
        src, dest = st["route"]
        try:
            res = translator.translate(txt, src=src, dest=dest)
            bot.reply_to(m, res.text)
        except Exception:
            bot.reply_to(m, "❌ Tarjima hozir ishlamadi. Keyinroq urinib ko‘ring yoki /menu orqali qaytadan tanlang.")
        return

    # Default: translit
    txt_norm = normalize_apostrophe(txt)
    if is_cyrillic_text(txt_norm):
        res = cyr_to_lat(txt_norm)
    else:
        res = lat_to_cyr(txt_norm)
    bot.reply_to(m, res)

bot.infinity_polling(skip_pending=True)

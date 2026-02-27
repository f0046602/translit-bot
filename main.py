import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN env var is missing")

bot = telebot.TeleBot(TOKEN)

# ---------------- Render uchun HTTP server ----------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    # Render health check ba'zida HEAD yuboradi
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ---------------- Apostrof normalizatsiya ----------------
def normalize_apostrophe(s: str) -> str:
    # hammasini bitta ko'rinishga keltiramiz: ’
    return (s.replace("`", "’")
             .replace("'", "’")
             .replace("ʻ", "’")   # U+02BB
             .replace("ʼ", "’")   # U+02BC
             .replace("‘", "’")
             .replace("´", "’")
             .replace("ʼ", "’"))

# ---------------- Translit (Lotin <-> Kirill) ----------------
LAT_MULTI = {
    # 2-harfli
    "sh": "ш", "ch": "ч", "yo": "ё", "yu": "ю", "ya": "я", "ng": "нг",
    "Sh": "Ш", "Ch": "Ч", "Yo": "Ё", "Yu": "Ю", "Ya": "Я", "Ng": "Нг",

    # o‘ / g‘ (har xil apostroflar normalizatsiyadan keyin o’/g’ bo'ladi)
    "o’": "ў", "g’": "ғ", "O’": "Ў", "G’": "Ғ",
    "oʻ": "ў", "gʻ": "ғ", "Oʻ": "Ў", "Gʻ": "Ғ",  # ehtiyot uchun
    "o‘": "ў", "g‘": "ғ", "O‘": "Ў", "G‘": "Ғ",  # ehtiyot uchun
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
        # 2 belgili kombinatsiyalarni tekshiramiz
        if i + 2 <= len(s):
            two = s[i:i+2]
            if two in LAT_MULTI:
                out.append(LAT_MULTI[two])
                i += 2
                continue
        out.append(LAT1.get(s[i], s[i]))
        i += 1
    return "".join(out)

# ---------------- Telegram handlers ----------------
@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Assalomu alekum! Men yuborilgan matini : Kirildi ↔️ Lotinga - Лотини ↔️ Крелга o‘girib beraman ✅")

@bot.message_handler(content_types=["text"])
def convert(m):
    txt = (m.text or "").strip()
    if not txt:
        return

    # apostrofni bir xil qilamiz (kirill->lotin uchun ham foydali)
    txt_norm = normalize_apostrophe(txt)

    if is_cyrillic_text(txt_norm):
        res = cyr_to_lat(txt_norm)
    else:
        res = lat_to_cyr(txt_norm)

    bot.reply_to(m, res)

bot.infinity_polling()

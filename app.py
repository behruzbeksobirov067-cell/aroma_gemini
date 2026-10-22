import csv, io, json, os, secrets, sqlite3, time
from collections import Counter, defaultdict, deque

from google import genai
types = genai.types
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
app.config.update(SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=1024 * 1024)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
DB = "aroma.db"
PROTOKOL = open("protokol.txt", encoding="utf-8").read()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if os.environ.get("GEMINI_API_KEY") else None

COLUMNS = ["nomi", "brend", "narx", "guruh", "fasl", "jins", "tavsif"]
JINSLAR = {"erkak", "ayol", "unisex"}
LIMIT_PER_HOUR = 10
hits = defaultdict(deque)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS perfumes(
            id INTEGER PRIMARY KEY, nomi TEXT, brend TEXT, narx INTEGER,
            guruh TEXT, fasl TEXT, jins TEXT, tavsif TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY, ts REAL, javoblar TEXT, tanlovlar TEXT)""")


def rate_limited(ip):
    now, q = time.time(), hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= LIMIT_PER_HOUR:
        return True
    q.append(now)
    return False


# ---------- Mijoz qismi ----------
@app.route("/")
def index():
    return render_template("index.html")


def score(p, fasl, hidlar):
    s = 0
    if fasl in (p["fasl"], "barcha") or p["fasl"] == "barcha":
        s += 2
    if any(h and h in p["guruh"].lower() for h in hidlar):
        s += 3
    return s


@app.route("/api/recommend", methods=["POST"])
def recommend():
    if rate_limited(request.remote_addr):
        return jsonify(xato="Juda ko'p so'rov. Bir ozdan keyin urinib ko'ring."), 429
    d = request.get_json(silent=True) or {}
    jins = str(d.get("jins", "")).lower()
    fasl = str(d.get("fasl", "barcha")).lower()
    kayfiyat = str(d.get("kayfiyat", ""))[:50]
    hidlar = [str(h).lower()[:30] for h in (d.get("hidlar") or [])][:6]
    izoh = str(d.get("izoh", ""))[:200].replace("<", "").replace(">", "")
    try:
        budjet = int(d.get("budjet") or 0)
    except (TypeError, ValueError):
        return jsonify(xato="Budjet raqam bo'lishi kerak."), 400
    if jins not in JINSLAR:
        return jsonify(xato="Kim uchun ekanini tanlang."), 400

    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM perfumes")]
    if not rows:
        return jsonify(xato="Katalog hali yuklanmagan."), 503
    rows = [r for r in rows if r["jins"] in (jins, "unisex") and (budjet <= 0 or r["narx"] <= budjet)]
    if not rows:
        return jsonify(xato="Bu budjetda mos atir topilmadi. Budjetni oshirib ko'ring."), 404
    rows.sort(key=lambda p: score(p, fasl, hidlar), reverse=True)
    nomzod = rows[:15]
    by_name = {p["nomi"]: p for p in nomzod}

    hidlar_matn = ", ".join(hidlar) or "ko'rsatilmagan"
    katalog = "\n".join(f'- {p["nomi"]} | {p["guruh"]} | {p["fasl"]} | {p["narx"]} so\'m | {p["tavsif"]}' for p in nomzod)
    mijoz = (f"Kim uchun: {jins}\nFasl: {fasl}\nKayfiyat: {kayfiyat}\n"
             f"Yoqtirgan hidlar: {hidlar_matn}\nBudjet: {budjet or 'cheklanmagan'}\nQo'shimcha: {izoh}")

    tavsiyalar, ai_ishladi = [], False
    if client:
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=f"Katalog:\n{katalog}\n\n<mijoz>\n{mijoz}\n</mijoz>",
                config=types.GenerateContentConfig(
                    system_instruction=PROTOKOL, max_output_tokens=2000,
                    response_mime_type="application/json"),
            )
            t = r.text
            data = json.loads(t[t.index("{"): t.rindex("}") + 1])
            for x in data.get("tavsiyalar", []):
                p = by_name.get(x.get("nomi"))          # katalogda yo'q atir tashlab yuboriladi
                if p and all(p["nomi"] != y["nomi"] for y in tavsiyalar):
                    tavsiyalar.append({"nomi": p["nomi"], "narx": p["narx"], "sabab": str(x.get("sabab", ""))[:300]})
            ai_ishladi = bool(tavsiyalar)
        except Exception as e:
            app.logger.warning("AI xatosi: %s", e)

    if not tavsiyalar:  # zaxira: AI ishlamasa ham natija chiqadi
        tavsiyalar = [{"nomi": p["nomi"], "narx": p["narx"], "sabab": p["tavsif"]} for p in nomzod[:3]]

    tavsiyalar = tavsiyalar[:3]
    with db() as con:
        con.execute("INSERT INTO requests(ts, javoblar, tanlovlar) VALUES(?,?,?)",
                    (time.time(), mijoz, json.dumps([t["nomi"] for t in tavsiyalar], ensure_ascii=False)))
    return jsonify(tavsiyalar=tavsiyalar, ai=ai_ishladi)


# ---------- Do'kon egasi paneli ----------
def admin_kerak():
    return session.get("admin") is True


@app.route("/admin", methods=["GET", "POST"])
def admin():
    xabar = request.args.get("xabar", "")
    if request.method == "POST" and "parol" in request.form:
        if ADMIN_PASSWORD and secrets.compare_digest(request.form["parol"], ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin"))
        xabar = "Parol noto'g'ri."
    if not admin_kerak():
        return render_template("admin.html", kirgan=False, xabar=xabar)
    with db() as con:
        atirlar = [dict(r) for r in con.execute("SELECT * FROM perfumes ORDER BY nomi")]
        reqs = con.execute("SELECT tanlovlar FROM requests").fetchall()
    top = Counter(n for r in reqs for n in json.loads(r["tanlovlar"])).most_common(5)
    return render_template("admin.html", kirgan=True, xabar=xabar, atirlar=atirlar, soni=len(reqs), top=top)


@app.route("/admin/upload", methods=["POST"])
def upload():
    if not admin_kerak():
        return redirect(url_for("admin"))
    f = request.files.get("fayl")
    if not f or not f.filename.lower().endswith(".csv"):
        return redirect(url_for("admin", xabar="CSV fayl tanlang."))
    try:
        reader = csv.DictReader(io.StringIO(f.read().decode("utf-8-sig")))
        if not reader.fieldnames or [c.strip() for c in reader.fieldnames][:7] != COLUMNS:
            return redirect(url_for("admin", xabar="Ustunlar noto'g'ri. Kerak: " + ", ".join(COLUMNS)))
        rows = []
        for i, r in enumerate(reader, start=2):
            jins = r["jins"].strip().lower()
            if not r["nomi"].strip() or jins not in JINSLAR:
                return redirect(url_for("admin", xabar=f"{i}-qatorda xato: nomi bo'sh yoki jins erkak/ayol/unisex emas."))
            rows.append((r["nomi"].strip(), r["brend"].strip(), int(r["narx"]), r["guruh"].strip().lower(),
                         r["fasl"].strip().lower(), jins, r["tavsif"].strip()))
        if not rows:
            return redirect(url_for("admin", xabar="Fayl bo'sh."))
    except (ValueError, UnicodeDecodeError, KeyError):
        return redirect(url_for("admin", xabar="Fayl o'qilmadi: narx raqam va fayl UTF-8 bo'lishi kerak."))
    with db() as con:
        con.execute("DELETE FROM perfumes")
        con.executemany("INSERT INTO perfumes(nomi,brend,narx,guruh,fasl,jins,tavsif) VALUES(?,?,?,?,?,?,?)", rows)
    return redirect(url_for("admin", xabar=f"{len(rows)} ta atir yuklandi."))


@app.route("/admin/chiqish")
def chiqish():
    session.clear()
    return redirect(url_for("admin"))


init_db()
if __name__ == "__main__":
    app.run(debug=False, port=5000)

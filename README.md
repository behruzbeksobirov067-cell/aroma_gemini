# Aroma: atir tanlash AI-maslahatchisi

Do'kon katalogini CSV bilan yuklaydi, mijoz 5 ta savolga javob beradi, Gemini katalogdan 3 ta atirni sabablari bilan tavsiya qiladi.

## Ishga tushirish
1. `python -m venv venv` va uni faollashtiring (Windows: `venv\Scripts\activate`, Mac/Linux: `source venv/bin/activate`)
2. `pip install -r requirements.txt`
3. `.env.example` ni `.env` ga nusxalab, qiymatlarni to'ldiring
4. `python app.py`, so'ng http://localhost:5000
5. http://localhost:5000/admin ga kirib `katalog_namuna.csv` ni yuklang

## Muhit o'zgaruvchilari
- `GEMINI_API_KEY`: Gemini API kaliti (aistudio.google.com dan bepul olinadi) (bo'lmasa, tizim AI'siz zaxira rejimida ishlaydi)
- `ADMIN_PASSWORD`: panel paroli (bo'sh bo'lsa, panelga kirib bo'lmaydi)
- `SECRET_KEY`: sessiya uchun tasodifiy matn
- `GEMINI_MODEL`: ixtiyoriy

## Xavfsizlik va chegaralash
- Kalit `.env` da, `.gitignore` orqali Git'ga tushmaydi
- Qoidalar `protokol.txt` da (system prompt); mijoz matni `<mijoz>` tegida, 200 belgi bilan cheklangan
- AI javobidagi har bir atir katalog bilan solishtiriladi, yo'qlari tashlanadi
- IP bo'yicha soatiga 10 ta so'rov; AI ishlamasa zaxira natija

## Ma'lum cheklovlar
- Bitta do'kon (ko'p do'konli rejim yo'q); so'rovlar soni xotirada, server qayta ishga tushsa nolga tushadi
- Admin formalarida CSRF tokeni yo'q (SameSite cookie bilan qisman himoyalangan)
- SQLite ko'p foydalanuvchiga mos emas (keyin PostgreSQL)
- Prompt injection'dan mutlaq himoya yo'q, faqat qatlamli kamaytirish

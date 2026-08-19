import os, json, requests, feedparser, html, re, sys
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CHANNEL = "@Crimea_frash_news"
PROXIES = {"http": None, "https": None}

def send_telegram(text, silent=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL, 
        "text": text, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True,
        "disable_notification": silent
    }
    r = requests.post(url, json=payload, proxies=PROXIES, timeout=30)
    mode = "ТИХО" if silent else "ЗВУК"
    print(f"Telegram ({mode}):", r.status_code)
    if r.status_code != 200:
        print(r.text[:500])

def get_weather(mode="morning"):
    cities = {"Севастополь": (44.6167, 33.5250), "Симферополь": (44.9521, 34.1024), "Ялта": (44.4958, 34.1569), "Керчь": (45.3564, 36.4670)}
    lines = []
    for name, (lat, lon) in cities.items():
        if mode == "morning":
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FSimferopol"
        else:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Europe%2FSimferopol"
        try:
            w = requests.get(url, proxies=PROXIES, timeout=30).json()
            if mode == "morning":
                t = w["current"]["temperature_2m"]
                tmax = w["daily"]["temperature_2m_max"][0]
                tmin = w["daily"]["temperature_2m_min"][0]
                lines.append(f"📍 {name}: <b>{t}°C</b> (день {tmax}°, ночь {tmin}°)")
            else:
                tmax = w["daily"]["temperature_2m_max"][1]
                tmin = w["daily"]["temperature_2m_min"][1]
                rain = w["daily"]["precipitation_probability_max"][1]
                rain_icon = "🌧" if rain > 30 else "☀️"
                lines.append(f"📍 {name}: день {tmax}°, ночь {tmin}°, {rain_icon} дождь: {rain}%")
        except Exception:
            lines.append(f"📍 {name}: нет данных")
    return "\n".join(lines)

def get_news(limit=10):
    with open("sources.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    items = []
    for src in cfg["sources"]:
        if not src.get("enabled", True): continue
        feed = feedparser.parse(src["url"])
        for e in feed.entries[:src.get("max_posts", limit)]:
            items.append({"title": e.title, "url": e.link})
    return items

def clean_post(text):
    for tag in ["</think>"]:
        if tag in text: text = text.split(tag)[-1]
    if "```" in text: text = re.sub(r"```[a-z]*\n?", "", text)
    return text.strip()

def groq_ask(prompt):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    try:
        m = requests.get("https://api.groq.com/openai/v1/models", headers=headers, proxies=PROXIES, timeout=15)
        ids = [x["id"] for x in m.json().get("data", [])] if m.status_code == 200 else []
    except Exception:
        ids = []
    bad = ["whisper", "guard", "safeguard", "orpheus"]
    good = [i for i in ids if not any(b in i for b in bad)]
    preferred = ["groq/compound-mini", "groq/compound", "llama-3.1-8b-instant"]
    candidates = [m for m in preferred if m in good] + [m for m in good if m not in preferred]
    for model in candidates[:5]:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2000}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, proxies=PROXIES, timeout=60)
            if r.status_code != 200: continue
            raw = r.json()["choices"][0]["message"]["content"]
            text = clean_post(raw)
            if len(text) > 50: return text
        except Exception:
            continue
    return None

# === ОПРЕДЕЛЯЕМ ВРЕМЯ (МСК = UTC+3) ===
msk_tz = timezone(timedelta(hours=3))
now_msk = datetime.now(msk_tz)
hour = now_msk.hour
minute = now_msk.minute

print(f"Текущее время МСК: {hour}:{minute:02d}")

# === ЛОГИКА ПО ВРЕМЕНИ ===
if hour == 6 and minute >= 45:
    print("=== 06:45: Тихий ночной дайджест ===")
    items = get_news(limit=15)
    news_list = "\n".join([f"{i+1}. {x['title']}" for i, x in enumerate(items[:10])])
    prompt = f"""Сделай очень краткий ночной дайджест из 5 самых интересных новостей.
    Новости: {news_list}
    Формат:
    🌙 САМОЕ ИНТЕРЕСНОЕ ЗА НОЧЬ
    1. [Заголовок] — [1 предложение сути]
    2. ... (всего 5 пунктов)
    Без воды, без ссылок (код добавит их сам)."""
    result = groq_ask(prompt)
    if result:
        send_telegram(html.escape(result), silent=True)

elif hour == 7:
    print("=== 07:00: Утренняя погода + новость ===")
    send_telegram(f"☀️ <b>ДОБРОЕ УТРО, КРЫМ!</b>\n\n🌤 Погода на сегодня:\n{get_weather('morning')}\n\nХорошего дня! #Крым #погода")

elif 8 <= hour <= 21:
    print(f"=== {hour}:00: Ежечасная новость ===")

elif hour == 22:
    print("=== 22:00: Вечерний прогноз + новость ===")
    send_telegram(f"🌙 <b>ПРОГНОЗ НА ЗАВТРА</b>\n\n{get_weather('evening')}\n\nСладких снов! #Крым #прогноз")

else:
    print("Вне часов публикации (23:00 - 06:00). Выход.")
    sys.exit(0)

# === ОБЩАЯ ЛОГИКА НОВОСТЕЙ (для 7-22 часов) ===
print("=== Генерация новости ===")
items = get_news(limit=10)
if not items:
    print("Нет новостей")
else:
    news_list = "\n".join([f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(items)])
    prompt = f"""Ты — редактор позитивного новостного канала о Крыме.
Свежие новости: {news_list}
ЗАДАНИЕ:
1. Выбери ОДНУ самую добрую и полезную новость (благоустройство, спорт, культура, туризм).
2. Игнорируй криминал, аварии, политику.
3. Структура:
🌟 ПОЗИТИВ ДНЯ
📰 [Короткий заголовок]
[2-3 предложения сути]
🎯 Что это даёт жителям Крыма:
• [пункт 1]
• [пункт a]
💬 Делитесь с близкими!
4. НЕ добавляй ссылку на источник.
5. Верни СТРОГО:
N: номер_новости
---
текст_поста"""
    result = groq_ask(prompt)
    if result:
        lines = result.split("\n")
        post_text, chosen_url = result, items[0]["url"]
        if lines and lines[0].strip().startswith("N:"):
            try:
                n = int(lines[0].strip().split(":")[1].strip())
                if 1 <= n <= len(items):
                    chosen_url = items[n-1]["url"]
                    sep_idx = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), -1)
                    if sep_idx > 0: post_text = "\n".join(lines[sep_idx+1:]).strip()
            except Exception: pass
        final = html.escape(post_text) + f'\n\n<a href="{chosen_url}">🔗 Ссылка на источник</a>'
        send_telegram(final[:4000], silent=False)
    else:
        print("Groq: не удалось получить пост")

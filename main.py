import os, json, requests, feedparser, html, re

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CHANNEL = "@Crimea_frash_news"
PROXIES = {"http": None, "https": None}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, proxies=PROXIES, timeout=30)
    print("Telegram:", r.status_code)
    if r.status_code != 200:
        print(r.text[:500])

def get_weather():
    cities = {
        "Севастополь": (44.6167, 33.5250),
        "Симферополь": (44.9521, 34.1024),
        "Ялта": (44.4958, 34.1569),
        "Керчь": (45.3564, 36.4670),
    }
    lines = []
    for name, (lat, lon) in cities.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FSimferopol"
        try:
            w = requests.get(url, proxies=PROXIES, timeout=30).json()
            t = w["current"]["temperature_2m"]
            tmax = w["daily"]["temperature_2m_max"][0]
            tmin = w["daily"]["temperature_2m_min"][0]
            lines.append(f"📍 {name}: <b>{t}°C</b> (день {tmax}°, ночь {tmin}°)")
        except Exception as e:
            lines.append(f"📍 {name}: нет данных")
    return "\n".join(lines)

def get_news():
    with open("sources.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    items = []
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        feed = feedparser.parse(src["url"])
        for e in feed.entries[:src.get("max_posts", 5)]:
            items.append({"title": e.title, "url": e.link})
    return items

def clean_post(text):
    for tag in ["</think>"]:
        if tag in text:
            text = text.split(tag)[-1]
    if "```" in text:
        text = re.sub(r"```[a-z]*\n?", "", text)
    return text.strip()

def groq_ask(prompt):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    try:
        m = requests.get("https://api.groq.com/openai/v1/models", headers=headers, proxies=PROXIES, timeout=15)
        ids = [x["id"] for x in m.json().get("data", [])] if m.status_code == 200 else []
    except Exception as ex:
        print("models error:", ex)
        ids = []
    bad = ["whisper", "guard", "safeguard", "orpheus"]
    good = [i for i in ids if not any(b in i for b in bad)]
    preferred = ["groq/compound-mini", "groq/compound", "llama-3.1-8b-instant"]
    candidates = [m for m in preferred if m in good] + [m for m in good if m not in preferred]
    print("candidates:", candidates[:5])
    for model in candidates[:5]:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2000}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, proxies=PROXIES, timeout=60)
            if r.status_code != 200:
                print(model, "->", r.status_code)
                continue
            raw = r.json()["choices"][0]["message"]["content"]
            text = clean_post(raw)
            if len(text) > 50:
                print("model ok:", model, "len:", len(text))
                return text
            print(model, "too short after clean")
        except Exception as ex:
            print(model, "error:", ex)
    return None

print("=== Погода ===")
weather = get_weather()
weather_post = f"☀️ <b>ДОБРОЕ УТРО, КРЫМ!</b>\n\n🌤 Погода на сегодня:\n{weather}\n\nХорошего и тёплого дня! #Крым #погода"
send_telegram(weather_post)

print("=== Новости ===")
items = get_news()
if not items:
    print("Нет новостей")
else:
    news_list = "\n".join([f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(items)])
    prompt = f"""Ты — редактор позитивного новостного Telegram-канала о Крыме.

Свежие новости (пронумерованы):
{news_list}

ЗАДАНИЕ:
1. Выбери ОДНУ самую добрую и полезную новость (благоустройство, спорт, культура, туризм, достижения, хорошие события).
2. Строго игнорируй криминал, аварии, политику, конфликты, судебные дела.
3. Напиши пост для Telegram в следующей структуре:

🌟 ПОЗИТИВ ДНЯ

📰 [Короткий цепляющий заголовок своими словами]

[2-3 предложения: что произошло и почему это интересно, простыми словами]

🎯 Что это даёт жителям Крыма:
• [пункт 1]
• [пункт 2]
• [пункт 3]

💬 Делитесь с близкими — пусть тоже порадуются!

4. НЕ добавляй ссылку на источник — её добавит код.
5. Верни ответ СТРОГО в формате:

N: номер_новости
---
текст_поста

Без пояснений, без markdown-блоков (```), без лишних слов."""

    result = groq_ask(prompt)
    if result:
        lines = result.split("\n")
        post_text = result
        chosen_url = items[0]["url"]
        if lines and lines[0].strip().startswith("N:"):
            try:
                n = int(lines[0].strip().split(":")[1].strip())
                if 1 <= n <= len(items):
                    chosen_url = items[n-1]["url"]
                    sep_idx = -1
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "---":
                            sep_idx = i
                            break
                    if sep_idx > 0:
                        post_text = "\n".join(lines[sep_idx+1:]).strip()
            except Exception as e:
                print("parse error:", e)
        post_text = html.escape(post_text)
        final = post_text + f'\n\n<a href="{chosen_url}">🔗 Ссылка на источник</a>'
        if len(final) > 4000:
            final = final[:3990] + "..."
        send_telegram(final)
    else:
        print("Groq: не удалось получить пост")

import os, json, requests, feedparser

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
CHANNEL = "@Crimea_frash_news"
PROXIES = {"http": None, "https": None}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHANNEL, "text": text}, proxies=PROXIES, timeout=30)
    print("Telegram:", r.status_code)
    if r.status_code != 200:
        print(r.text[:300])

def get_weather():
    url = "https://api.open-meteo.com/v1/forecast?latitude=44.95&longitude=34.10&current_weather=true&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FSimferopol"
    w = requests.get(url, proxies=PROXIES, timeout=30).json()
    t = w["current_weather"]["temperature"]
    tmax = w["daily"]["temperature_2m_max"][0]
    tmin = w["daily"]["temperature_2m_min"][0]
    return f"🌤 Сейчас в Крыму: {t}°C. Днём до {tmax}°, ночью {tmin}°."

def get_news():
    with open("sources.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    items = []
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        feed = feedparser.parse(src["url"])
        for e in feed.entries[:src.get("max_posts", 5)]:
            items.append(f"- {e.title} ({e.link})")
    return "\n".join(items)

def groq_ask(prompt):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    try:
        m = requests.get("https://api.groq.com/openai/v1/models", headers=headers, proxies=PROXIES, timeout=15)
        ids = [x["id"] for x in m.json().get("data", [])] if m.status_code == 200 else []
    except Exception as ex:
        print("models error:", ex)
        ids = []
    bad = ["whisper", "guard", "safeguard"]
    good = [i for i in ids if not any(b in i for b in bad)]
    print("candidates:", good[:5])
    for model in good[:5]:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2000}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, proxies=PROXIES, timeout=60)
            if r.status_code != 200:
                print(model, "->", r.status_code)
                continue
            text = r.json()["choices"][0]["message"]["content"]
            if text and len(text.strip()) > 10:
                print("model ok:", model)
                return text
        except Exception as ex:
            print(model, "error:", ex)
    return None

print("=== Погода ===")
weather = get_weather()
send_telegram("☀️ ДОБРОЕ УТРО, КРЫМ!\n\n" + weather + "\n\nХорошего и тёплого дня! #Крым #погода")

print("=== Новости ===")
news = get_news()
prompt = f"""Ты — редактор позитивного новостного канала о Крыме.
Свежие новости:
{news}

Выбери ОДНУ самую добрую и полезную новость (благоустройство, спорт, культура, туризм, хорошие события).
Игнорируй криминал, аварии и политику.
Напиши пост для Telegram в тёплом стиле, 2-4 предложения, с эмодзи.
В конце обязательно добавь: 🔗 Источник: [ссылка на новость]
Максимум 1000 символов. Верни только текст поста."""
post = groq_ask(prompt)
if post:
    send_telegram(post)
else:
    print("Groq: не удалось получить пост")


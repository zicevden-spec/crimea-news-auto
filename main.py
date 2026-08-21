import os, json, requests, feedparser, html, re, sys, random, time
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
CHANNEL = "@Crimea_frash_news"
PROXIES = {"http": None, "https": None}
HIST_FILE = "history.json"
STATE_FILE = "daily_state.json"

MOTIVATIONAL_PHRASES = [
    "Каждый новый день — это шанс сделать что-то хорошее. Начни с улыбки! 😊",
    "Маленькие шаги каждый день приводят к большим переменам. Верь в себя! 💪",
    "Сегодня идеальный день, чтобы сделать кого-то счастливее. Начни с себя! ✨",
    "Успех — это сумма маленьких усилий, повторяющихся изо дня в день. 🌱",
    "Пусть этот день принесёт тебе новые возможности и приятные сюрпризы! 🌞"
]
CALM_THOUGHTS = [
    "Спокойной ночи. Пусть завтрашний день принесёт только светлые мысли и добрые вести. 🌙",
    "Отдыхай с лёгким сердцем. Всё, что должно случиться, случится в лучшее время. ✨",
    "Ночь создана для того, чтобы отпустить тревоги и набраться сил для новых свершений. 🌌",
    "Мудрость приходит в тишине. Пусть ваш сон будет крепким, а утро — добрым. 🦉",
    "Закрой глаза и представь самое тёплое место. Завтра будет новый, прекрасный день. 💫"
]
FORMATS = [
    {"name": "standard", "intro": "🌟 ПОЗИТИВ ДНЯ", "benefits_header": "🎯 Что это даёт жителям Крыма:", "benefits_items": ["• [пункт 1]", "• [пункт 2]", "• [пункт 3]"], "footer": "💬 Делитесь с близкими! Перешлите это сообщение.\n🔗 Наш канал: @Crimea_frash_news"},
    {"name": "friendly", "intro": "✨ ХОРОШАЯ НОВОСТЬ!", "benefits_header": "🌈 Почему это здорово:", "benefits_items": ["→ [пункт 1]", "→ [пункт 2]", "→ [пункт 3]"], "footer": "💬 Расскажите об этом знакомым!\n✉️ Подписывайтесь: @Crimea_frash_news"},
    {"name": "compact", "intro": "📰 КРАТКО О ГЛАВНОМ", "benefits_header": "💡 Главное:", "benefits_items": ["✓ [пункт 1]", "✓ [пункт 2]", "✓ [пункт 3]"], "footer": "🔄 Поделитесь с друзьями!\n📲 Канал: @Crimea_frash_news"}
]

def save_state(state):
    if not GITHUB_TOKEN: return
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.system("git config --global user.email 'bot@crimea.local'")
    os.system("git config --global user.name 'Crimea Bot'")
    os.system("git add " + STATE_FILE)
    os.system("git commit -m 'update daily state [skip ci]'")
    os.system("git push")

def save_history(url):
    if not GITHUB_TOKEN: return
    history = []
    if os.path.exists(HIST_FILE):
        try:
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                history = json.load(f).get("posted_urls", [])
        except: pass
    if url not in history: history.append(url)
    history = history[-50:]
    hist_data = {"posted_urls": history, "last_post_time": time.time()}
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(hist_data, f, ensure_ascii=False, indent=2)
    os.system("git add " + HIST_FILE)
    os.system("git commit -m 'update history [skip ci]'")
    os.system("git push")

def send_telegram_text(text, silent=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True, "disable_notification": silent}
    r = requests.post(url, json=payload, proxies=PROXIES, timeout=30)
    print(f"Telegram text ({'ТИХО' if silent else 'ЗВУК'}):", r.status_code)

def send_telegram_photo(photo_url, caption, silent=False):
    try:
        img_resp = requests.get(photo_url, proxies=PROXIES, timeout=30)
        if img_resp.status_code != 200:
            send_telegram_text(caption + "\n\n(Картинка не загрузилась)", silent)
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {"photo": ("image.jpg", img_resp.content, "image/jpeg")}
        data = {"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML", "disable_notification": "true" if silent else "false"}
        r = requests.post(url, files=files, data=data, proxies=PROXIES, timeout=30)
        print(f"Telegram photo ({'ТИХО' if silent else 'ЗВУК'}):", r.status_code)
    except Exception as e:
        send_telegram_text(caption + "\n\n(Ошибка фото)", silent)

def get_weather(mode="morning"):
    cities = {"Севастополь": (44.6167, 33.5250), "Симферополь": (44.9521, 34.1024), "Ялта": (44.4958, 34.1569), "Керчь": (45.3564, 36.4670)}
    lines = []
    for name, (lat, lon) in cities.items():
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&{'current=temperature_2m&' if mode=='morning' else ''}daily=temperature_2m_max,temperature_2m_min{',precipitation_probability_max' if mode=='evening' else ''}&timezone=Europe%2FSimferopol"
        try:
            w = requests.get(url, proxies=PROXIES, timeout=30).json()
            if mode == "morning":
                lines.append(f"📍 {name}: <b>{w['current']['temperature_2m']}°C</b> (день {w['daily']['temperature_2m_max'][0]}°, ночь {w['daily']['temperature_2m_min'][0]}°)")
            else:
                rain = w["daily"]["precipitation_probability_max"][1]
                lines.append(f"📍 {name}: день {w['daily']['temperature_2m_max'][1]}°, ночь {w['daily']['temperature_2m_min'][1]}°, {'🌧' if rain>30 else '☀️'} дождь: {rain}%")
        except: lines.append(f"📍 {name}: нет данных")
    return "\n".join(lines)

def get_news(limit=20, source_filter=None):
    with open("sources.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    items = []
    for src in cfg["sources"]:
        if not src.get("enabled", True): continue
        if source_filter and src.get("name") != source_filter: continue
        feed = feedparser.parse(src["url"])
        for e in feed.entries[:src.get("max_posts", limit)]:
            image_url = None
            if hasattr(e, 'media_content') and e.media_content: image_url = e.media_content[0].get('url')
            elif hasattr(e, 'media_thumbnail') and e.media_thumbnail: image_url = e.media_thumbnail[0].get('url')
            items.append({"title": e.title, "url": e.link, "image": image_url, "source": src.get("name")})
    return items

def clean_post(text):
    if "</think>" in text: text = text.split("</think>")[-1]
    if "```" in text: text = re.sub(r"```[a-z]*\n?", "", text)
    return text.strip()

def groq_ask(prompt):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    try:
        m = requests.get("https://api.groq.com/openai/v1/models", headers=headers, proxies=PROXIES, timeout=15)
        ids = [x["id"] for x in m.json().get("data", [])] if m.status_code == 200 else []
    except: ids = []
    good = [i for i in ids if not any(b in i for b in ["whisper", "guard", "safeguard", "orpheus"])]
    preferred = ["groq/compound-mini", "groq/compound", "llama-3.1-8b-instant"]
    candidates = [m for m in preferred if m in good] + [m for m in good if m not in preferred]
    for model in candidates[:5]:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2000}, proxies=PROXIES, timeout=60)
            if r.status_code == 200:
                text = clean_post(r.json()["choices"][0]["message"]["content"])
                if len(text) > 50: return text
        except: continue
    return None

# === MAIN LOGIC ===
msk_tz = timezone(timedelta(hours=3))
now_msk = datetime.now(msk_tz)
hour = now_msk.hour
today_str = now_msk.strftime("%Y-%m-%d")

state = {"date": today_str, "digest": False, "morning": False, "latest_news": False, "evening": False}
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if loaded.get("date") == today_str: state = loaded
    except: pass

# 1. DIGEST (Until 10:00)
if hour < 10 and not state.get("digest"):
    print("=== Утренний дайджест ===")
    items = get_news(15)
    news_lines = [f"{i+1}. {x['title']}" for i, x in enumerate(items[:10])]
    news_text = "\n".join(news_lines)
    prompt = f"""Сделай краткий дайджест из 5 новостей.
Новости:
{news_text}
Формат:
🌙 САМОЕ ИНТЕРЕСНОЕ ЗА НОЧЬ
1. [Заголовок] — [1 предложение]
...(всего 5 пунктов)"""
    res = groq_ask(prompt)
    if res: 
        send_telegram_text(html.escape(res), silent=True)
        state["digest"] = True
        save_state(state)
    sys.exit(0)

# 2. MORNING (Until 10:00)
if hour < 10 and state.get("digest") and not state.get("morning"):
    print("=== Утренняя погода и мотивация ===")
    motivational = random.choice(MOTIVATIONAL_PHRASES)
    send_telegram_text(f"☀️ <b>ДОБРОЕ УТРО, КРЫМ!</b>\n\n{motivational}\n\n🌤 Погода на сегодня:\n{get_weather('morning')}\n\nХорошего дня! #Крым #погода")
    state["morning"] = True
    save_state(state)
    sys.exit(0)

# 3. LATEST NEWS (After 22:00)
if hour >= 22 and not state.get("latest_news"):
    print("=== Самая свежая новость ===")
    all_items = get_news(20)
    posted_urls = []
    if os.path.exists(HIST_FILE):
        try: posted_urls = json.load(open(HIST_FILE, "r", encoding="utf-8")).get("posted_urls", [])
        except: pass
    fresh_items = [i for i in all_items if i["url"] not in posted_urls]
    if not fresh_items: sys.exit(0)
    target_items = fresh_items[:3]
    news_lines = [f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(target_items)]
    news_list = "\n".join(news_lines)
    fmt = random.choice(FORMATS)
    prompt = f"""Ты — редактор позитивного канала о Крыме.
Вот самые свежие новости дня: {news_list}
ЗАДАНИЕ:
1. Выбери самую свежую добрую новость. Игнорируй криминал и политику.
2. Структура:
{fmt['intro']}
📰 [Короткий заголовок]
[2-3 предложения сути]
{fmt['benefits_header']}
{chr(10).join(fmt['benefits_items'])}
{fmt['footer']}
3. НЕ добавляй ссылку на источник.
4. Верни СТРОГО:
N: номер_новости
---
текст_поста"""
    result = groq_ask(prompt)
    if result:
        lines = result.split("\n")
        post_text, chosen_url, chosen_image = result, fresh_items[0]["url"], fresh_items[0].get("image")
        if lines and lines[0].strip().startswith("N:"):
            try:
                n = int(lines[0].strip().split(":")[1].strip())
                if 1 <= n <= len(target_items):
                    chosen = target_items[n-1]
                    chosen_url, chosen_image = chosen["url"], chosen.get("image")
                sep = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), -1)
                if sep > 0: post_text = "\n".join(lines[sep+1:]).strip()
            except: pass
        final = html.escape(post_text) + f'\n\n<a href="{chosen_url}">🔗 Ссылка на источник</a>'
        if chosen_image and len(final) < 1000: send_telegram_photo(chosen_image, final, silent=False)
        else: send_telegram_text(final[:4000], silent=False)
        save_history(chosen_url)
        state["latest_news"] = True
        save_state(state)
    sys.exit(0)

# 4. EVENING FORECAST (After 22:00)
if hour >= 22 and state.get("latest_news") and not state.get("evening"):
    print("=== Вечерний прогноз и спокойной ночи ===")
    calm_thought = random.choice(CALM_THOUGHTS)
    send_telegram_text(f"🌙 <b>ПРОГНОЗ НА ЗАВТРА</b>\n\n{get_weather('evening')}\n\n{calm_thought}\n\nСладких снов, Крым! #Крым #спокойнойночи")
    state["evening"] = True
    save_state(state)
    sys.exit(0)

# 5. HOURLY NEWS (10:00 - 21:59)
if 10 <= hour <= 21:
    last_post_time = 0
    if os.path.exists(HIST_FILE):
        try: last_post_time = json.load(open(HIST_FILE, "r", encoding="utf-8")).get("last_post_time", 0)
        except: pass
    if time.time() - last_post_time < 1800:
        print("Пост уже был в последние 30 минут, пропускаем")
        sys.exit(0)
    source_filter = "vesti-k" if hour in [12, 13, 14] else None
    all_items = get_news(20, source_filter)
    posted_urls = []
    if os.path.exists(HIST_FILE):
        try: posted_urls = json.load(open(HIST_FILE, "r", encoding="utf-8")).get("posted_urls", [])
        except: pass
    fresh_items = [i for i in all_items if i["url"] not in posted_urls]
    if not fresh_items: sys.exit(0)
    fmt = random.choice(FORMATS)
    news_lines = [f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(fresh_items)]
    news_list = "\n".join(news_lines)
    prompt = f"""Ты — редактор позитивного канала о Крыме.
Свежие новости: {news_list}
ЗАДАНИЕ:
1. Выбери ОДНУ добрую новость. Игнорируй криминал и политику.
2. Структура:
{fmt['intro']}
📰 [Короткий заголовок]
[2-3 предложения сути]
{fmt['benefits_header']}
{chr(10).join(fmt['benefits_items'])}
{fmt['footer']}
3. НЕ добавляй ссылку на источник.
4. Верни СТРОГО:
N: номер_новости
---
текст_поста"""
    result = groq_ask(prompt)
    if result:
        lines = result.split("\n")
        post_text, chosen_url, chosen_image = result, fresh_items[0]["url"], fresh_items[0].get("image")
        if lines and lines[0].strip().startswith("N:"):
            try:
                n = int(lines[0].strip().split(":")[1].strip())
                if 1 <= n <= len(fresh_items):
                    chosen = fresh_items[n-1]
                    chosen_url, chosen_image = chosen["url"], chosen.get("image")
                sep = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), -1)
                if sep > 0: post_text = "\n".join(lines[sep+1:]).strip()
            except: pass
        final = html.escape(post_text) + f'\n\n<a href="{chosen_url}">🔗 Ссылка на источник</a>'
        if chosen_image and len(final) < 1000: send_telegram_photo(chosen_image, final, silent=False)
        else: send_telegram_text(final[:4000], silent=False)
        save_history(chosen_url)
    sys.exit(0)

print("Вне часов публикации. Выход.")
sys.exit(0)

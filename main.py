import os, json, requests, feedparser, html, re, sys, random, time
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
CHANNEL = "@Crimea_frash_news"
PROXIES = {"http": None, "https": None}
HIST_FILE = "history.json"

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
    {"name": "compact", "intro": "📰 КРАТКО О ГЛАВНОМ", "benefits_header": "💡Главное:", "benefits_items": ["✓ [пункт 1]", "✓ [пункт 2]", "✓ [пункт 3]"], "footer": "🔄 Поделитесь с друзьями!\n📲 Канал: @Crimea_frash_news"}
]

def save_history(url):
    if not GITHUB_TOKEN: return
    history = []
    if os.path.exists(HIST_FILE):
        try:
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                history = json.load(f).get("posted_urls", [])
        except: pass
    if url not in history:
        history.append(url)
    history = history[-50:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump({"posted_urls": history}, f, ensure_ascii=False, indent=2)
    os.system("git config --global user.email 'bot@crimea.local'")
    os.system("git config --global user.name 'Crimea Bot'")
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
    # Удаляем любые блоки размышлений ( Qwen,  и т.д.)
    text = re.sub(r'(?s)<think>.*?</think>', '', text)
    text = re.sub(r'(?s)</think>.*?</think>', '', text)
    text = re.sub(r'(?s)<thinking>.*?</thinking>', '', text)
    
    # Если текст начинается с тега размышления, но не закрыт (обрыв лимита)
    if text.strip().startswith('<think') or text.strip().startswith('<')
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
            # Увеличили max_tokens до 8000, чтобы модель не задыхалась
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 8000}, proxies=PROXIES, timeout=60)
            if r.status_code == 200:
                text = clean_post(r.json()["choices"][0]["message"]["content"])
                if len(text) > 50: return text
        except: continue
    return None

msk_tz = timezone(timedelta(hours=3))
now_msk = datetime.now(msk_tz)
hour, minute = now_msk.hour, now_msk.minute
print(f"Текущее время МСК: {hour}:{minute:02d}")

is_latest_news = False
source_filter = None

if hour == 6 and minute >= 45:
    print("=== 06:45: Тихий дайджест ===")
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
    if res: send_telegram_text(html.escape(res), silent=True)
    sys.exit(0)
elif hour == 7:
    print("=== 07:00: Утро ===")
    motivational = random.choice(MOTIVATIONAL_PHRASES)
    send_telegram_text(f"☀️ <b>ДОБРОЕ УТРО, КРЫМ!</b>\n\n{motivational}\n\n🌤 Погода на сегодня:\n{get_weather('morning')}\n\nХорошего дня! #Крым #погода")
elif hour == 22 and minute == 0:
    print("=== 22:00: Самая свежая новость ===")
    is_latest_news = True
elif hour == 22 and minute == 15:
    print("=== 22:15: Вечерний прогноз и спокойной ночи ===")
    calm_thought = random.choice(CALM_THOUGHTS)
    send_telegram_text(f"🌙 <b>ПРОГНОЗ НА ЗАВТРА</b>\n\n{get_weather('evening')}\n\n{calm_thought}\n\nСладких снов, Крым! #Крым #спокойнойночи")
    sys.exit(0)
elif hour in [12, 13, 14] and minute == 30:
    print(f"=== {hour}:30: Новость из Вести-К ===")
    source_filter = "vesti-k"
elif 8 <= hour <= 21:
    print(f"=== {hour}:00: Ежечасная новость ===")
else:
    print("Вне часов публикации. Выход.")
    sys.exit(0)

print("=== Генерация новости ===")
all_items = get_news(20, source_filter)
posted_urls = []
last_post_time = 0

if os.path.exists(HIST_FILE):
    try: 
        hist_data = json.load(open(HIST_FILE, "r", encoding="utf-8"))
        posted_urls = hist_data.get("posted_urls", [])
        last_post_time = hist_data.get("last_post_time", 0)
    except: pass

# Защита от дублей: если пост уже был в последние 30 минут, пропускаем (кроме утра и вечера)
if time.time() - last_post_time < 1800 and not is_latest_news and hour != 7:
    print("Пост уже был в последние 30 минут, пропускаем")
    sys.exit(0)

fresh_items = [i for i in all_items if i["url"] not in posted_urls]
if not fresh_items:
    print(f"Все последние новости ({source_filter or 'все'}) уже опубликованы. Ждём обновлений.")
    sys.exit(0)

print(f"Найдено {len(fresh_items)} свежих новостей.")
fmt = random.choice(FORMATS)

if is_latest_news:
    target_items = fresh_items[:3]
    news_lines = [f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(target_items)]
    news_list = "\n".join(news_lines)
    prompt = f"""Ты — редактор позитивного канала о Крыме.
Вот самые свежие новости дня: {news_list}
ЗАДАНИЕ:
1. Выбери самую свежую (первую или вторую) добрую новость. Игнорируй криминал и политику.
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
else:
    news_lines = [f"{i+1}. {x['title']} ({x['url']})" for i, x in enumerate(fresh_items)]
    news_list = "\n".join(news_lines)
    prompt = f"""Ты — редактор позитивного канала о Крыме.
Свежие новости: {news_list}
ЗАДАНИЕ:
1. Выбери ОДНУ добрую новость (благоустройство, спорт, культура, туризм). Игнорируй криминал и политику.
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
            target = target_items if is_latest_news else fresh_items
            if 1 <= n <= len(target):
                chosen = target[n-1]
                chosen_url, chosen_image = chosen["url"], chosen.get("image")
            sep = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), -1)
            if sep > 0: post_text = "\n".join(lines[sep+1:]).strip()
        except: pass
    final = html.escape(post_text) + f'\n\n<a href="{chosen_url}">🔗 Ссылка на источник</a>'
    if chosen_image and len(final) < 1000:
        send_telegram_photo(chosen_image, final, silent=False)
    else:
        send_telegram_text(final[:4000], silent=False)
    
    save_history(chosen_url)
    
    # Сохраняем время публикации для защиты от дублей
    if os.path.exists(HIST_FILE):
        hist = json.load(open(HIST_FILE, "r", encoding="utf-8"))
        hist["last_post_time"] = time.time()
        json.dump(hist, open(HIST_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.system("git add " + HIST_FILE)
        os.system("git commit -m 'update timestamp [skip ci]'")
        os.system("git push")
else:
    print("Groq: не удалось получить пост")


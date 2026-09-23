# Тестовая публикация: берёт свежую новость с картинкой из RSS и шлёт в Telegram.
# Использование:
#   python test_post.py --dry-run          # без токенов, показать что будет опубликовано
#   TELEGRAM_NEWS_BOT_TOKEN=xxx GROQ_API_KEY=yyy python test_post.py            # тест в отдельный чат
#   ... python test_post.py --to-channel   # полный тест в канал @Crimea_frash_news (ОСТОРОЖНО!)
import os, sys, html

DRY = "--dry-run" in sys.argv
TO_CHANNEL = "--to-channel" in sys.argv
TEST_CHAT = os.environ.get("TEST_CHAT_ID", "")  # id/username тестового чата

import main as m  # импортируем уже исправленный код (get_news, send_telegram_photo, groq_ask)

if not DRY:
    if TEST_CHAT:
        m.CHANNEL = TEST_CHAT
    elif not TO_CHANNEL:
        print("Укажите TEST_CHAT_ID=<id> для теста в личный чат, или --to-channel для публикации в канал.")
        sys.exit(1)
    if not m.TELEGRAM_TOKEN:
        print("Нужен TELEGRAM_NEWS_BOT_TOKEN (или запускайте с --dry-run)")
        sys.exit(1)

items = m.get_news(20)
with_img = [i for i in items if i["image"]]
print(f"Новостей всего: {len(items)}, с картинками: {len(with_img)}")
if not with_img:
    print("Картинки не найдены ни у одной новости — тест прерван."); sys.exit(1)

target = with_img[0]
print(f"\nТестируем новость: [{target['source']}] {target['title']}\nКартинка: {target['image']}\n")

fmt = m.FORMATS[0]
post_text = None
if m.GROQ_KEY:
    prompt = f"""Ты — редактор позитивного канала о Крыме.
Свежая новость: {target['title']} ({target['url']})
ЗАДАНИЕ: Сделай короткий позитивный пост. Структура:
{fmt['intro']}
📰 [Короткий заголовок]
[2-3 предложения сути]
{fmt['benefits_header']}
• благо для жителей
• настроение
• польза
{fmt['footer']}
Верни только текст поста."""
    post_text = m.groq_ask(prompt)

if not post_text:
    # Фолбэк без Groq — чтобы проверить именно доставку картинки
    post_text = f"{fmt['intro']}\n📰 {target['title']}\n\nТЕСТОВАЯ ПУБЛИКАЦИЯ (проверка картинок из источников)\n\n{fmt['footer']}"

caption = html.escape(post_text) + f'\n\n<a href="{target["url"]}">🔗 Ссылка на источник</a>'

if DRY:
    print("=== DRY RUN: пост, который был бы отправлен ===\n")
    print(caption)
    import requests
    r = requests.head(target["image"], timeout=15, allow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"})
    print(f"\nПроверка доступности картинки: HTTP {r.status_code} | {r.headers.get('content-type')}")
    sys.exit(0)

m.send_telegram_photo(target["image"], caption, silent=True)
print("\n✅ Тестовая публикация отправлена (без истории, тихо). Проверьте чат.")

import asyncio
import json
import os
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

from config import API_ID, API_HASH, CHANNEL, POSTS_LIMIT, UPDATE_INTERVAL

app = Flask(__name__)
CORS(app)

PHOTOS_DIR = 'photos'
os.makedirs(PHOTOS_DIR, exist_ok=True)

CACHE_FILE = 'posts.json'
cached_posts = []


def load_cache():
    global cached_posts
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cached_posts = json.load(f)
        print(f"Загружено {len(cached_posts)} постов из кеша")


def save_cache(posts):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


async def fetch_from_telegram():
    print("Получаем посты из Telegram...")
    client = TelegramClient('session', API_ID, API_HASH)
    await client.start()
    posts = []
    try:
        async for message in client.iter_messages(CHANNEL, limit=POSTS_LIMIT):
            if not message.text and not message.media:
                continue
            post = {
                'id': message.id,
                'date': message.date.strftime('%d.%m.%Y'),
                'time': message.date.strftime('%H:%M'),
                'text': message.text or '',
                'photo': None,
                'views': message.views or 0,
            }
            if isinstance(message.media, MessageMediaPhoto):
                photo_name = f'{message.id}.jpg'
                photo_path = os.path.join(PHOTOS_DIR, photo_name)
                if not os.path.exists(photo_path):
                    try:
                        await client.download_media(message, photo_path)
                    except Exception as e:
                        print(f"Ошибка фото: {e}")
                if os.path.exists(photo_path):
                    post['photo'] = f'/photos/{photo_name}'
            posts.append(post)
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await client.disconnect()
    return posts


def update_posts():
    global cached_posts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        posts = loop.run_until_complete(fetch_from_telegram())
        if posts:
            cached_posts = posts
            save_cache(posts)
            print(f"Обновлено {len(posts)} постов")
    finally:
        loop.close()


@app.route('/posts')
def get_posts():
    return jsonify({'status': 'ok', 'count': len(cached_posts), 'posts': cached_posts})


@app.route('/photos/<filename>')
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'posts_count': len(cached_posts)})


if __name__ == '__main__':
    load_cache()
    print("Первое получение постов...")
    update_posts()
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_posts, 'interval', seconds=UPDATE_INTERVAL)
    scheduler.start()
    print("Сервер запущен: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
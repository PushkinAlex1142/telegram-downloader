import os
import base64
import asyncio
from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
from telethon import TelegramClient as AsyncTelegramClient  # для асинхронного использования

app = Flask(__name__)

# Восстанавливаем файл сессии
session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))

# Получаем API_ID и API_HASH из Render
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Асинхронная функция для скачивания файла
async def download_file(chat, message_id):
    try:
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            msg = await client.get_messages(chat, ids=message_id)

            if msg is None:
                return {"status": "error", "message": f"Message with ID {message_id} not found."}

            if msg.media:
                path = await client.download_media(msg)
                return {"status": "ok", "file_path": path}
            else:
                return {"status": "error", "message": "Нет медиа в сообщении"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Асинхронная функция для получения последних сообщений
async def get_last_messages(chat):
    try:
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            messages = await client.get_messages(chat, limit=10)
            result = []
            for msg in messages:
                result.append({
                    "id": msg.id,
                    "text": msg.text,
                    "has_media": bool(msg.media)
                })
            return {"status": "ok", "messages": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Главная страница
@app.route('/')
def index():
    return '✅ Сервер Telegram работает!'

# Скачивание медиа по chat и message_id
@app.route('/download', methods=['POST'])
def download():
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(download_file(chat, message_id))
    
    return jsonify(result)

# Получение последних 10 сообщений из чата
@app.route('/last_messages', methods=['GET'])
def last_messages():
    chat = request.args.get("chat")
    if not chat:
        return jsonify({"status": "error", "message": "Параметр 'chat' обязателен"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(get_last_messages(chat))
    
    return jsonify(result)

# Запуск сервера
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

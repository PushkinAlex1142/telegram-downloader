import os
import base64
from flask import Flask, request, jsonify
from telethon.sync import TelegramClient

app = Flask(__name__)

# Восстанавливаем файл сессии
session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))

# Получаем API_ID и API_HASH из Render
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

@app.route('/')
def index():
    return '✅ Сервер Telegram работает!'

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")

    try:
        with TelegramClient("session", API_ID, API_HASH) as client:
            msg = client.get_messages(chat, ids=message_id)
            if msg and msg.media:
                path = client.download_media(msg)
                return jsonify({"status": "ok", "file_path": path})
            else:
                return jsonify({"status": "error", "message": "Нет медиа в сообщении"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

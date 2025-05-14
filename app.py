import os
import base64
import asyncio
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

async def download_file(chat, message_id):
    try:
        async with TelegramClient("session", API_ID, API_HASH) as client:
            # Fetch message by ID
            msg = await client.get_messages(chat, ids=message_id)
            
            # Debug: Check message details
            print(f"Message details: {msg}")
            print(f"Message type: {type(msg)}")

            messages = client.get_messages("@McKPartnersBot", limit=10)
            for msg in messages:
                print(f"{msg.id}: {msg.text} | media: {msg.media}")

            if msg is None:
                return {"status": "error", "message": f"Message with ID {message_id} not found."}
                
            if msg.media:
                print(f"Media found: {msg.media}")
                path = await client.download_media(msg)
                return {"status": "ok", "file_path": path}
            else:
                # If no media, return error
                return {"status": "error", "message": "No media in this message"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.route('/')
def index():
    return '✅ Сервер Telegram работает!'

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")
    
    # Запускаем асинхронную задачу в основном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(download_file(chat, message_id))
    
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

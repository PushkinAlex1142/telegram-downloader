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
            msg = await client.get_messages(chat, ids=message_id)
            if msg and msg.media:
                path = await client.download_media(msg)
                return {"status": "ok", "file_path": path}
            else:
                return {"status": "error", "message": "Нет медиа в сообщении"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Method to upload an audio file from a user (via POST request)
@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Check if the request contains a file
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"})

        file = request.files['file']
        
        # Check if the file is an audio file (you can extend the validation as needed)
        if file and file.filename.endswith('.mp3'):
            # Save the file temporarily
            file_path = os.path.join('uploads', file.filename)
            file.save(file_path)
            
            # Now you can process the file (upload it, store it, etc.)
            # For example, let's just return the path where it's saved
            return jsonify({"status": "ok", "file_path": file_path})
        else:
            return jsonify({"status": "error", "message": "Invalid file type, only MP3 files are allowed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

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

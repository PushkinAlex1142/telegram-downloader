from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

# Константы из переменных окружения
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

@app.route("/")
def index():
    return "✅ Telegram Downloader is running"

@app.route("/download", methods=["POST"])
def download():
    try:
        data = request.get_json()
        chat = data.get("chat")
        message_id = data.get("message_id")

        if not chat or not message_id:
            return jsonify({"error": "Missing 'chat' or 'message_id'"}), 400

        with TelegramClient("session", API_ID, API_HASH) as client:
            message = client.get_messages(chat, ids=message_id)

            if not message or not message.media:
                return jsonify({"error": "No media found in that message"}), 404

            path = client.download_media(message)
            return jsonify({"status": "ok", "file_path": path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

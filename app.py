from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import base64
import os

app = Flask(__name__)

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']

# Decode session file
session_b64 = os.environ.get("SESSION_B64")
with open("session.session", "wb") as f:
    f.write(base64.b64decode(session_b64))

@app.route("/")
def index():
    return "✅ Telegram Downloader is running!"

@app.route("/last_messages", methods=["GET"])
def last_messages():
    chat = request.args.get("chat")
    if not chat:
        return jsonify({"error": "Chat username or ID is required"}), 400

    try:
        with TelegramClient("session", API_ID, API_HASH) as client:
            messages = client.get_messages(chat, limit=10)
            output = []
            for msg in messages:
                output.append({
                    "id": msg.id,
                    "text": msg.text,
                    "has_media": bool(msg.media)
                })

            return jsonify({"messages": output, "status": "ok"})
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

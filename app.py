import os
import asyncio
from flask import Flask, request, jsonify
from telethon import TelegramClient
from telethon.sessions import StringSession

# Setup from environment variables
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')  # Optional if already authorized

app = Flask(__name__)

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()

    chat = data.get("chat")
    message_id = data.get("message_id")

    if not chat or not message_id:
        return jsonify({"error": "Missing 'chat' or 'message_id'"}), 400

    try:
        # Run async download logic inside sync route
        path = asyncio.run(download_media(chat, message_id))
        return jsonify({"status": "success", "file": path})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


async def download_media(chat, message_id):
    session = StringSession()  # In-memory session (or load from env if needed)
    async with TelegramClient(session, API_ID, API_HASH) as client:
        await client.start()  # If not logged in, will ask for code in terminal
        msg = await client.get_messages(chat, ids=message_id)

        if not msg or not msg.media:
            raise ValueError("No media found in that message.")

        file_path = await msg.download_media()
        return file_path


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

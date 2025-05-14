import os
import asyncio
from flask import Flask, request, jsonify
from telethon import TelegramClient
from telethon.sessions import StringSession

# Load environment variables from Render
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")  # Must be set in Render dashboard

# Create in-memory session client
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Flask setup
app = Flask(__name__)

async def get_file(chat, message_id):
    await client.start()
    message = await client.get_messages(chat, ids=message_id)
    
    if not message or not message.document:
        return None
    
    path = await message.download_media()
    return path

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    chat = data.get("chat")
    message_id = data.get("message_id")

    try:
        path = asyncio.run(get_file(chat, message_id))
        if path:
            return jsonify({"status": "success", "file_path": path})
        else:
            return jsonify({"status": "error", "message": "No document found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

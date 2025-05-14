import os
import asyncio
from flask import Flask, request, jsonify
from telethon.sync import TelegramClient

app = Flask(__name__)

# Use an async function for handling the download
async def download_file(chat, message_id):
    try:
        # Initialize the Telegram client
        async with TelegramClient('session', int(os.getenv("API_ID")), os.getenv("API_HASH")) as client:
            # Get the file from the message
            message = await client.get_messages(chat, ids=message_id)
            file_path = await message.download_media(file="./downloads")
        return file_path
    except Exception as e:
        return str(e)

@app.route('/')
def index():
    return '✅ Telegram Downloader Server is running!'

@app.route('/download', methods=['POST'])
def download():
    # Extract the chat and message_id from the request
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")

    # Check if chat and message_id are provided
    if not chat or not message_id:
        return jsonify({"error": "Missing 'chat' or 'message_id'"}), 400

    # Run the async function using asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_path = loop.run_until_complete(download_file(chat, message_id))
        if isinstance(file_path, str) and file_path.startswith("error"):
            return jsonify({"error": file_path}), 500
        return jsonify({"status": "ok", "file_path": file_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # important for Render
    app.run(host='0.0.0.0', port=port)

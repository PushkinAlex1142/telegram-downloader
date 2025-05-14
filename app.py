from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

@app.route('/')
def index():
    return '✅ Telegram Downloader Server is running!'

@app.route('/download', methods=['POST'])
def download():
    try:
        # Extract the chat and message_id from the request
        data = request.json
        chat = data.get("chat")
        message_id = data.get("message_id")

        # Check if chat and message_id are provided
        if not chat or not message_id:
            return jsonify({"error": "Missing 'chat' or 'message_id'"}), 400

        # Initialize the Telegram client
        with TelegramClient('session', int(os.getenv("API_ID")), os.getenv("API_HASH")) as client:
            # Get the file from the message
            message = client.get_messages(chat, ids=message_id)
            file_path = message.download_media(file="./downloads")

        return jsonify({"status": "ok", "file_path": file_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # important for Render
    app.run(host='0.0.0.0', port=port)

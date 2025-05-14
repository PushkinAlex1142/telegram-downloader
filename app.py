from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

@app.route('/')
def index():
    return '✅ Telegram Downloader Server is running!'

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    
    # Retrieve chat and message_id from the incoming JSON data
    chat = data.get("chat")
    message_id = data.get("message_id")
    
    if not chat or not message_id:
        return jsonify({"status": "error", "message": "Chat and message_id are required!"}), 400

    try:
        # Initialize the client with the saved session
        with TelegramClient('session', int(os.getenv("API_ID")), os.getenv("API_HASH")) as client:
            # Get the message with the specified message_id from the specified chat
            message = client.get_messages(chat, ids=message_id)

            # Check if the message has a document (file) attached
            if not message or not message.document:
                return jsonify({"status": "error", "message": "No document found in the message."}), 404
            
            # Download the media (file) attached to the message
            file_path = message.download_media()
            
            return jsonify({"status": "success", "file_path": file_path}), 200
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # important for Render
    app.run(host='0.0.0.0', port=port)

from flask import Flask
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

client = TelegramClient("session", API_ID, API_HASH)

@app.route('/')
def index():
    return 'Server is running!'

@app.route('/download', methods=['POST'])
def download():
    client.connect()
    if not client.is_user_authorized():
        return "Session not authorized"
    messages = client.get_messages('me', limit=3)
    for msg in messages:
        print(msg.text)
    client.disconnect()
    return "Download done!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

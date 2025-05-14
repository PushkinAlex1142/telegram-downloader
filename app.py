from flask import Flask
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

@app.route('/')
def index():
    return '✅ Telegram Downloader Server is running!'

@app.route('/download')
def download():
    # Create client using the saved session
    with TelegramClient('session', int(os.getenv("API_ID")), os.getenv("API_HASH")) as client:
        # Example action: print your own username
        me = client.get_me()
        print(f"Logged in as: {me.username}")

        # TODO: Replace with your actual download logic here
        # For example: client.download_media(...)
        
    return '✅ Download completed (or simulated)!'

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # important for Render
    app.run(host='0.0.0.0', port=port)

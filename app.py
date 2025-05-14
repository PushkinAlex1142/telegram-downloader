from flask import Flask
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

# Get environment variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

# Create the client once (not inside the route)
client = TelegramClient("session", API_ID, API_HASH)

@app.route('/')
def index():
    return 'Server is running!'

@app.route('/download')
def download():
    client.connect()

    if not client.is_user_authorized():
        client.send_code_request(PHONE_NUMBER)
        return "Session not authorized. Go check the logs or add authorization logic."

    # Example download: Get messages from saved messages
    messages = client.get_messages('me', limit=3)
    for msg in messages:
        print(msg.text)

    client.disconnect()
    return "Download done!"

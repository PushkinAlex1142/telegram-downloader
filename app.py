import asyncio
from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

client = TelegramClient('session', API_ID, API_HASH)

@app.route('/')
def index():
    return 'Server is running!'

@app.route('/download', methods=['POST'])
def download():
    # Get the data from the POST request
    data = request.json
    message_id = int(data.get("message_id"))
    chat = data.get("chat")
    
    # Function to download the file asynchronously
    async def get_file():
        await client.start(PHONE_NUMBER)
        message = await client.get_messages(chat, ids=message_id)
        file_path = await message.download_media(file="./downloads")
        return file_path

    # Run the async function in the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    path = loop.run_until_complete(get_file())
    
    return jsonify({"status": "ok", "path": path})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

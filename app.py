from flask import Flask, request, jsonify
from telethon.sync import TelegramClient
import os

app = Flask(__name__)

api_id = int(os.getenv("20099671"))
api_hash = os.getenv("a7b9fa280f33e964d52c3fe374fbaef5")
phone = os.getenv("+79912984740")  # Only needed for first login

client = TelegramClient('session_name', api_id, api_hash)

@app.route('/download', methods=['POST'])
def download_file():
    data = request.json
    message_id = int(data.get("message_id"))
    chat = data.get("chat")

    async def get_file():
        await client.start(phone)
        message = await client.get_messages(chat, ids=message_id)
        file_path = await message.download_media(file="./downloads")
        return file_path

    with client:
        path = client.loop.run_until_complete(get_file())

    return jsonify({"status": "ok", "path": path})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

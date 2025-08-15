import os
import base64
import asyncio
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify, send_from_directory
from telethon.sync import TelegramClient
from telethon import TelegramClient as AsyncTelegramClient

app = Flask(__name__)

session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

def connect_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Берём ключ из переменной окружения на Render (GOOGLE_CREDENTIALS в Base64 → строка JSON)
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Google credentials not found in environment variables")

    creds_dict = json.loads(base64.b64decode(creds_json))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client


async def update_whitelist(chat_id, sheet_name, worksheet_name="Sheet1"):
    async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
        participants = await client.get_participants(chat_id)
        whitelist_ids = [[str(p.id)] for p in participants]  # Каждая ID в новой строке

        gclient = connect_gsheet()
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)
        sheet.clear()
        sheet.update('A1', whitelist_ids)

        return {"status": "ok", "count": len(whitelist_ids)}


@app.route('/update_whitelist', methods=['POST'])
def update_whitelist_route():
    data = request.json
    chat_id = data.get("chat_id")
    sheet_name = data.get("sheet_name")
    worksheet_name = data.get("worksheet_name", "Sheet1")

    if not chat_id or not sheet_name:
        return jsonify({"status": "error", "message": "chat_id and sheet_name are required"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(update_whitelist(chat_id, sheet_name, worksheet_name))

    return jsonify(result)


async def download_file(chat, message_id):
    try:
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            msg = await client.get_messages(chat, ids=message_id)

            if msg is None:
                return {"status": "error", "message": f"Message with ID {message_id} not found."}

            if msg.media:
                path = await client.download_media(msg)
                return {"status": "ok", "file_path": path}
            else:
                return {"status": "error", "message": "No media in the message."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def get_last_messages(chat):
    try:
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            messages = await client.get_messages(chat, limit=3)
            result = []
            for msg in messages:
                result.append({
                    "id": msg.id,
                    "text": msg.text,
                    "has_media": bool(msg.media)
                })
            return {"status": "ok", "messages": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return '✅ Telegram server works!'

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(download_file(chat, message_id))
    
    return jsonify(result)

@app.route('/last_messages', methods=['GET'])
def last_messages():
    chat = request.args.get("chat")
    if not chat:
        return jsonify({"status": "error", "message": "Parameter 'chat' is required"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(get_last_messages(chat))
    
    return jsonify(result)

@app.route('/download_file/<path:file_path>', methods=['GET'])
def serve_file(file_path):
    try:
        return send_from_directory(os.getcwd(), file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

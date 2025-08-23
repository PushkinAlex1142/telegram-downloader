import os
import base64
import asyncio
import json
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify, send_from_directory
from telethon.sync import TelegramClient
from telethon import TelegramClient as AsyncTelegramClient

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Создание сессии из переменной окружения
session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Максимальный размер файла для скачивания (в байтах)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ

def connect_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Берём ключ из переменной окружения на Render (GOOGLE_CREDENTIALS в Base64 → строка JSON)
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Google credentials not found in environment variables")

    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

async def check_user_in_whitelist(username, sheet_name, worksheet_name="WhiteList"):
    """Проверяет, есть ли пользователь в белом списке Google Sheets"""
    try:
        gclient = connect_gsheet()
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)
        
        # Получаем все значения из колонки A (usernames)
        usernames = sheet.col_values(1)
        
        # Проверяем наличие username в списке
        if username in usernames:
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking whitelist: {e}")
        return False

async def update_whitelist(chat_id, sheet_name, worksheet_name="WhiteList"):
    async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
        participants = await client.get_participants(chat_id)

        ids = []
        for user in participants:
            ids.append([user.username])

        gclient = connect_gsheet()
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)

        sheet.clear()
        sheet.update("A1", [["username"]])
        if ids:
            sheet.update("A2", ids)
        return {"status": "ok", "count": len(ids)}

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

async def download_file(chat, message_id, username=None, sheet_name=None):
    """Скачивает файл с проверкой белого списка и размера файла"""
    try:
        # Проверка белого списка, если указаны username и sheet_name
        if username and sheet_name:
            is_whitelisted = await check_user_in_whitelist(username, sheet_name)
            if not is_whitelisted:
                return {"status": "error", "message": "User not in whitelist"}
        
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            entity = await client.get_entity(chat)
            msg = await client.get_messages(entity, ids=message_id)

            if msg is None:
                return {"status": "error", "message": f"Message with ID {message_id} not found."}

            if msg.media:
                # Проверяем размер файла перед скачиванием
                if msg.media.document:
                    file_size = msg.media.document.size
                    if file_size > MAX_FILE_SIZE:
                        return {
                            "status": "error", 
                            "message": f"File too large ({file_size} bytes). Maximum allowed: {MAX_FILE_SIZE} bytes",
                            "file_size": file_size,
                            "max_size": MAX_FILE_SIZE
                        }
                
                # Скачиваем файл
                path = await client.download_media(msg)
                file_size = os.path.getsize(path) if os.path.exists(path) else 0
                
                return {
                    "status": "ok", 
                    "file_path": path,
                    "file_size": file_size,
                    "file_name": os.path.basename(path),
                    "download_url": f"/download_file/{os.path.basename(path)}"
                }
            else:
                return {"status": "error", "message": "No media in the message."}
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return {"status": "error", "message": str(e)}

async def get_last_messages(chat, limit=10):
    try:
        async with AsyncTelegramClient("session", API_ID, API_HASH) as client:
            messages = await client.get_messages(chat, limit=limit)
            result = []
            for msg in messages:
                file_info = None
                if msg.media and hasattr(msg.media, 'document'):
                    file_info = {
                        "size": msg.media.document.size,
                        "name": getattr(msg.media.document.attributes[0], 'file_name', 'unknown') if msg.media.document.attributes else 'unknown',
                        "mime_type": msg.media.document.mime_type
                    }
                
                result.append({
                    "id": msg.id,
                    "text": msg.text,
                    "has_media": bool(msg.media),
                    "file_info": file_info,
                    "date": msg.date.isoformat() if msg.date else None,
                    "from_user": msg.sender_id if msg.sender_id else None
                })
            return {"status": "ok", "messages": result}
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return '✅ Telegram server works!'

@app.route('/download', methods=['POST'])
def download():
    """Эндпоинт для скачивания файла с проверкой белого списка"""
    data = request.json
    chat = data.get("chat")
    message_id = data.get("message_id")
    username = data.get("username")  # username пользователя для проверки
    sheet_name = data.get("sheet_name")  # название Google Sheet для проверки
    
    if not chat or not message_id:
        return jsonify({"status": "error", "message": "chat and message_id are required"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(download_file(chat, message_id, username, sheet_name))
    
    return jsonify(result)

@app.route('/last_messages', methods=['GET'])
def last_messages():
    chat = request.args.get("chat")
    limit = int(request.args.get("limit", 10))
    
    if not chat:
        return jsonify({"status": "error", "message": "Parameter 'chat' is required"}), 400

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(get_last_messages(chat, limit))
    
    return jsonify(result)

@app.route('/download_file/<path:file_path>', methods=['GET'])
def serve_file(file_path):
    """Отдает скачанный файл для n8n"""
    try:
        # Безопасная проверка пути
        safe_path = os.path.basename(file_path)
        directory = os.getcwd()
        file_full_path = os.path.join(directory, safe_path)
        
        if not os.path.exists(file_full_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        return send_from_directory(directory, safe_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/file_info/<path:file_path>', methods=['GET'])
def file_info(file_path):
    """Информация о файле для n8n"""
    try:
        safe_path = os.path.basename(file_path)
        file_full_path = os.path.join(os.getcwd(), safe_path)
        
        if not os.path.exists(file_full_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        return jsonify({
            "status": "ok",
            "file_name": safe_path,
            "file_size": os.path.getsize(file_full_path),
            "created_at": os.path.getctime(file_full_path),
            "modified_at": os.path.getmtime(file_full_path)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Очистка скачанных файлов (для n8n)"""
    try:
        files_deleted = 0
        for filename in os.listdir(os.getcwd()):
            if filename != "session.session" and os.path.isfile(filename):
                os.remove(filename)
                files_deleted += 1
                
        return jsonify({"status": "ok", "files_deleted": files_deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

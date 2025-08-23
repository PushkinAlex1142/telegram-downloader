import os
import base64
import asyncio
import json
import gspread
import logging
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient, events

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Создание сессии из переменной окружения
session_data = os.getenv("SESSION")
if session_data:
    try:
        with open("session.session", "wb") as f:
            f.write(base64.b64decode(session_data))
        logger.info("Session file created successfully")
    except Exception as e:
        logger.error(f"Error creating session file: {e}")

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")

# Максимальный размер файла для скачивания (в байтах)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ

# Глобальная переменная для хранения информации о последнем файле
last_downloaded_file = None

def connect_gsheet():
    """Подключение к Google Sheets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            raise Exception("Google credentials not found in environment variables")
        
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}")
        raise

async def check_user_in_whitelist(username, sheet_name, worksheet_name="WhiteList"):
    """Проверяет, есть ли пользователь в белом списке Google Sheets"""
    try:
        if not username or not sheet_name:
            return False
            
        gclient = connect_gsheet()
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)
        
        # Получаем все значения из колонки A (usernames)
        usernames = sheet.col_values(1)
        
        # Проверяем наличие username в списке (игнорируем заголовок)
        if username in usernames[1:]:
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking whitelist: {e}")
        return False

async def download_media_file(event, sheet_name):
    """Скачивает медиафайл из сообщения"""
    global last_downloaded_file
    
    try:
        # Получаем информацию о отправителе
        sender = await event.get_sender()
        username = sender.username
        
        # Проверяем белый список
        if not await check_user_in_whitelist(username, sheet_name):
            logger.info(f"User {username} not in whitelist, skipping download")
            return
        
        # Проверяем размер файла
        if hasattr(event.media, 'document') and event.media.document:
            file_size = event.media.document.size
            if file_size > MAX_FILE_SIZE:
                logger.info(f"File too large ({file_size} bytes), skipping download")
                return
        
        # Скачиваем файл
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        path = await event.download_media(file=download_dir)
        if not path:
            logger.error("Failed to download file")
            return
            
        file_size = os.path.getsize(path) if os.path.exists(path) else 0
        
        # Сохраняем информацию о файле
        last_downloaded_file = {
            "file_path": path,
            "file_name": os.path.basename(path),
            "file_size": file_size,
            "download_url": f"/download_file/{os.path.basename(path)}",
            "download_time": datetime.now().isoformat(),
            "chat_id": event.chat_id,
            "sender_id": sender.id,
            "username": username
        }
        
        logger.info(f"File downloaded successfully: {last_downloaded_file['file_name']}")
        
    except Exception as e:
        logger.error(f"Error downloading media file: {e}")

async def start_telegram_client():
    """Запускает Telegram клиент и настраивает обработчики"""
    try:
        client = TelegramClient("session", API_ID, API_HASH)
        
        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            # Проверяем, что это личное сообщение и содержит медиа
            if event.is_private and event.media:
                sheet_name = os.getenv("GOOGLE_SHEET_NAME")
                if sheet_name:
                    await download_media_file(event, sheet_name)
        
        await client.start()
        logger.info("Telegram client started successfully")
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error starting Telegram client: {e}")

def run_telegram_client():
    """Запускает Telegram клиент в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_telegram_client())

# Запускаем Telegram клиент в фоновом потоке
import threading
telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
telegram_thread.start()

@app.route('/')
def index():
    return '✅ Telegram server works!'

@app.route('/last_file', methods=['GET'])
def get_last_file():
    """Возвращает информацию о последнем скачанном файле"""
    global last_downloaded_file
    
    if not last_downloaded_file:
        return jsonify({
            "status": "error", 
            "message": "No files downloaded yet"
        }), 404
    
    # Проверяем, существует ли файл
    file_path = last_downloaded_file.get('file_path')
    file_exists = file_path and os.path.exists(file_path)
    
    response_data = {
        "status": "ok",
        "file": {
            **last_downloaded_file,
            "file_exists": file_exists
        }
    }
    
    # Добавляем текущий размер, если файл существует
    if file_exists:
        response_data["file"]["current_size"] = os.path.getsize(file_path)
    
    return jsonify(response_data)

@app.route('/download_file/<path:filename>', methods=['GET'])
def serve_file(filename):
    """Отдает скачанный файл для n8n"""
    try:
        # Безопасная проверка пути
        safe_filename = os.path.basename(filename)
        directory = "downloads"
        file_full_path = os.path.join(directory, safe_filename)
        
        if not os.path.exists(file_full_path):
            return jsonify({"status": "error", "message": "File not found"}), 404
            
        return send_from_directory(directory, safe_filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Очистка скачанных файлов (для n8n)"""
    global last_downloaded_file
    
    try:
        files_deleted = 0
        download_dir = "downloads"
        
        if os.path.exists(download_dir):
            for filename in os.listdir(download_dir):
                file_path = os.path.join(download_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        files_deleted += 1
                        logger.info(f"Deleted file: {filename}")
                    except Exception as e:
                        logger.error(f"Error deleting file {filename}: {e}")
        
        # Сбрасываем информацию о последнем файле
        last_downloaded_file = None
                
        return jsonify({"status": "ok", "files_deleted": files_deleted})
    except Exception as e:
        logger.error(f"Error in cleanup endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

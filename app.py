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
telegram_client = None

def connect_gsheet():
    """Подключение к Google Sheets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            logger.warning("Google credentials not found in environment variables")
            return None
        
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}")
        return None

async def check_user_in_whitelist(username, sheet_name, worksheet_name="WhiteList"):
    """Проверяет, есть ли пользователь в белом списке Google Sheets"""
    try:
        if not username or not sheet_name:
            return False
            
        gclient = connect_gsheet()
        if not gclient:
            return False
            
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

async def download_media_file(event):
    """Скачивает медиафайл из сообщения"""
    global last_downloaded_file
    
    try:
        # Получаем информацию о отправителе
        sender = await event.get_sender()
        username = sender.username if sender and hasattr(sender, 'username') else "unknown"
        
        logger.info(f"Received media from {username}")
        
        # Проверяем белый список (если настроен)
        sheet_name = os.getenv("GOOGLE_SHEET_NAME")
        if sheet_name:
            if not await check_user_in_whitelist(username, sheet_name):
                logger.info(f"User {username} not in whitelist, skipping download")
                return
        else:
            logger.info("No Google sheet name configured, skipping whitelist check")
        
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
            "sender_id": sender.id if sender else None,
            "username": username
        }
        
        logger.info(f"File downloaded successfully: {last_downloaded_file['file_name']} ({file_size} bytes)")
        
    except Exception as e:
        logger.error(f"Error downloading media file: {e}")

async def setup_telegram_client():
    """Настраивает и запускает Telegram клиент"""
    global telegram_client
    
    try:
        telegram_client = TelegramClient("session", API_ID, API_HASH)
        
        @telegram_client.on(events.NewMessage(incoming=True))
        async def handler(event):
            # Проверяем, что это личное сообщение и содержит медиа
            if event.is_private and event.media:
                logger.info("Received private message with media")
                await download_media_file(event)
            elif event.is_private:
                logger.info(f"Received private message without media: {event.text}")
        
        await telegram_client.start()
        logger.info("Telegram client started successfully")
        logger.info(f"Logged in as: {await telegram_client.get_me()}")
        
        # Запускаем клиент в фоновом режиме
        await telegram_client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error setting up Telegram client: {e}")

def run_telegram_client():
    """Запускает Telegram клиент"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(setup_telegram_client())
    except Exception as e:
        logger.error(f"Error running Telegram client: {e}")
    finally:
        loop.close()

# Запускаем Telegram клиент в фоновом потоке
telegram_thread = None

@app.before_first_request
def start_telegram_background():
    """Запускает Telegram клиент при первом запросе"""
    global telegram_thread
    if telegram_thread is None or not telegram_thread.is_alive():
        telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
        telegram_thread.start()
        logger.info("Telegram client thread started")

@app.route('/')
def index():
    return '✅ Telegram server works! Use /last_file to check downloaded files.'

@app.route('/last_file', methods=['GET'])
def get_last_file():
    """Возвращает информацию о последнем скачанном файле"""
    global last_downloaded_file
    
    if not last_downloaded_file:
        return jsonify({
            "status": "error", 
            "message": "No files downloaded yet. Send a file to the bot first."
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

@app.route('/status', methods=['GET'])
def status():
    """Проверяет статус Telegram клиента"""
    global telegram_client, telegram_thread
    
    status_info = {
        "flask_status": "running",
        "telegram_client_status": "running" if telegram_client and telegram_client.is_connected() else "not connected",
        "telegram_thread_status": "alive" if telegram_thread and telegram_thread.is_alive() else "not alive",
        "last_file": bool(last_downloaded_file)
    }
    
    return jsonify(status_info)

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
    import threading
    # Запускаем Telegram клиент в фоновом режиме
    telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
    telegram_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

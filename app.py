import os
import base64
import asyncio
import json
import gspread
import logging
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify, send_from_directory
from telethon import TelegramClient, events
import threading

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Создание сессии из переменной окружения
session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))
    logger.info("Session file created successfully")

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ
last_downloaded_file = None
telegram_client = None

def connect_gsheet():
    """Подключение к Google Sheets"""
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            logger.warning("Google credentials not found")
            return None
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Google Sheets connection error: {e}")
        return None

async def check_user_in_whitelist(username, sheet_name, worksheet_name="WhiteList"):
    """Проверка пользователя в whitelist"""
    try:
        if not username or not sheet_name:
            return False
        gclient = connect_gsheet()
        if not gclient:
            return False
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)
        usernames = sheet.col_values(1)
        return username in usernames[1:]
    except Exception as e:
        logger.error(f"Whitelist check error: {e}")
        return False

async def download_media_file(event):
    """Скачивание медиа-файла"""
    global last_downloaded_file
    try:
        sender = await event.get_sender()
        username = getattr(sender, "username", "unknown")
        sheet_name = os.getenv("GOOGLE_SHEET_NAME")
        if sheet_name and not await check_user_in_whitelist(username, sheet_name):
            logger.info(f"User {username} not in whitelist")
            return

        if hasattr(event.media, "document") and event.media.document.size > MAX_FILE_SIZE:
            logger.info("File too large, skipping")
            return

        os.makedirs("downloads", exist_ok=True)
        path = await event.download_media(file="downloads")
        if not path:
            logger.error("Failed to download file")
            return

        last_downloaded_file = {
            "file_path": path,
            "file_name": os.path.basename(path),
            "file_size": os.path.getsize(path),
            "download_url": f"/download_file/{os.path.basename(path)}",
            "download_time": datetime.now().isoformat(),
            "username": username
        }
        logger.info(f"Downloaded file: {last_downloaded_file['file_name']}")
    except Exception as e:
        logger.error(f"Download error: {e}")

async def setup_telegram_client():
    """Настройка и запуск Telegram клиента"""
    global telegram_client
    telegram_client = TelegramClient("session", API_ID, API_HASH)

    @telegram_client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if event.is_private and event.media:
            logger.info(f"New private media message from {event.sender_id}")
            await download_media_file(event)

    await telegram_client.start()
    logger.info(f"Telegram client started as {await telegram_client.get_me()}")
    await telegram_client.run_until_disconnected()

def run_telegram_client():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_telegram_client())
    loop.close()

# Flask эндпоинты
@app.route('/last_file', methods=['GET'])
def get_last_file():
    global last_downloaded_file
    if not last_downloaded_file:
        return jsonify({"status": "error", "message": "No files downloaded yet"}), 404
    file_exists = os.path.exists(last_downloaded_file["file_path"])
    response = {**last_downloaded_file, "file_exists": file_exists}
    if file_exists:
        response["current_size"] = os.path.getsize(last_downloaded_file["file_path"])
    return jsonify({"status": "ok", "file": response})

@app.route('/download_file/<path:filename>', methods=['GET'])
def serve_file(filename):
    safe_filename = os.path.basename(filename)
    file_full_path = os.path.join("downloads", safe_filename)
    if not os.path.exists(file_full_path):
        return jsonify({"status": "error", "message": "File not found"}), 404
    return send_from_directory("downloads", safe_filename, as_attachment=True)

if __name__ == '__main__':
    telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
    telegram_thread.start()
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

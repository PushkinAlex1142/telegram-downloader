import os
import base64
import asyncio
import json
import gspread
import logging
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify, send_from_directory, request
from telethon import TelegramClient, events
import threading
import requests

# ---------------- Логирование ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------- Telegram session ----------------
session_data = os.getenv("SESSION")
if session_data:
    with open("session.session", "wb") as f:
        f.write(base64.b64decode(session_data))
    logger.info("Session file created successfully")

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 МБ

DOWNLOAD_DIR = "downloads"
LAST_FILE_JSON = "last_file.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

telegram_client = None

# ---------------- Google Sheets ----------------
def connect_gsheet():
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
    try:
        if not username:
            return False
        gclient = connect_gsheet()
        if not gclient:
            return False
        sheet = gclient.open(sheet_name).worksheet(worksheet_name)
        usernames = [u.strip().lower() for u in sheet.col_values(1)[1:]]  # убрать заголовок и пробелы
        return username.lower() in usernames
    except Exception as e:
        logger.error(f"Whitelist check error: {e}")
        return False

# ---------------- Save last file ----------------
def save_last_file_info(data):
    with open(LAST_FILE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f)

# ---------------- Webhook для N8N ----------------
def trigger_n8n_webhook(file_info):
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("N8N webhook URL not set")
        return
    try:
        response = requests.post(webhook_url, json=file_info, timeout=5)
        if response.status_code == 200:
            logger.info("N8N webhook triggered successfully")
        else:
            logger.warning(f"N8N webhook returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Error triggering N8N webhook: {e}")

# ---------------- Telegram ----------------
async def download_media_file(event):
    try:
        sender = await event.get_sender()
        username = getattr(sender, "username", "unknown")
        sheet_name = os.getenv("GOOGLE_SHEET_NAME")
        if not sheet_name or not await check_user_in_whitelist(username, sheet_name):
            logger.info(f"User {username} not in whitelist, skipping download")
            return

        if hasattr(event.media, "document") and event.media.document.size > MAX_FILE_SIZE:
            logger.info(f"File too large ({event.media.document.size} bytes), skipping")
            return

        path = await event.download_media(file=DOWNLOAD_DIR)
        if not path:
            logger.error("Failed to download file")
            return

        last_file = {
            "file_path": path,
            "file_name": os.path.basename(path),
            "file_size": os.path.getsize(path),
            "download_url": f"/download_file/{os.path.basename(path)}",
            "download_time": datetime.now().isoformat(),
            "username": username
        }
        save_last_file_info(last_file)
        logger.info(f"File downloaded successfully: {last_file['file_name']}")

        # ✅ Trigger webhook
        trigger_n8n_webhook(last_file)

    except Exception as e:
        logger.error(f"Error downloading media file: {e}")

async def setup_telegram_client():
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

# ---------------- Flask routes ----------------
@app.route('/last_file', methods=['GET'])
def get_last_file():
    if not os.path.exists(LAST_FILE_JSON):
        return jsonify({"status": "error", "message": "No files downloaded yet"}), 404
    with open(LAST_FILE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    file_exists = os.path.exists(data["file_path"])
    data["file_exists"] = file_exists
    if file_exists:
        data["current_size"] = os.path.getsize(data["file_path"])
    return jsonify({"status": "ok", "file": data})

@app.route('/download_file/<path:filename>', methods=['GET'])
def serve_file(filename):
    safe_filename = os.path.basename(filename)
    file_full_path = os.path.join(DOWNLOAD_DIR, safe_filename)
    if not os.path.exists(file_full_path):
        return jsonify({"status": "error", "message": "File not found"}), 404
    return send_from_directory(DOWNLOAD_DIR, safe_filename, as_attachment=True)

@app.route('/delete_file/<path:filename>', methods=['POST'])
def delete_file(filename):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(DOWNLOAD_DIR, safe_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted file: {safe_filename}")
        return jsonify({"status": "ok", "message": f"{safe_filename} deleted"})
    else:
        return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    files_deleted = 0
    for filename in os.listdir(DOWNLOAD_DIR):
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                files_deleted += 1
                logger.info(f"Deleted file: {filename}")
            except Exception as e:
                logger.error(f"Error deleting file {filename}: {e}")
    # Сброс last_file.json
    if os.path.exists(LAST_FILE_JSON):
        os.remove(LAST_FILE_JSON)
    return jsonify({"status": "ok", "files_deleted": files_deleted})

# ---------------- Main ----------------
if __name__ == '__main__':
    telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
    telegram_thread.start()
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

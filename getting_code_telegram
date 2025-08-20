from telethon.sync import TelegramClient
import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

client = TelegramClient("session", API_ID, API_HASH)

client.connect()
if not client.is_user_authorized():
    client.send_code_request(PHONE_NUMBER)
    code = input("Enter the code you received: ")
    client.sign_in(PHONE_NUMBER, code)

print("✅ Logged in and session saved.")
client.disconnect()

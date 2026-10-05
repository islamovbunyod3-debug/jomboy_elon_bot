import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import sqlite3
from aiohttp import web
import asyncio

# 1. BOT SOZLAMALARI
API_TOKEN = '8645108254:AAG2xvLWF8AaNS4m7-mMK9yDo4gnIKP8GDY'  # Yangi token
ADMIN_ID = 6985111317  # Sizning ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 2. MA'LUMOTLAR BAZASI
conn = sqlite3.connect('jomboy_elonlari.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    invited_count INTEGER DEFAULT 0
)
''')
conn.commit()

# 3. HANDLERLAR (START VA PROFIL)
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply("👋 Assalomu alaykum! 'Jomboy Elonlari' guruhining rasmiy botiga xush kelibsiz.\n\n"
                        "📊 Guruhga odam qo'shing va pul mukofotlarini oling! "
                        "Guruh ichida /mening_profilim buyrug'ini yuborib natijangizni tekshirishingiz mumkin.")

@dp.message_handler(commands=['mening_profilim'])
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    count = row[0] if row else 0
    
    text = (f"👤 **Foydalanuvchi:** {message.from_user.get_mention(as_html=True)}\n"
            f"📊 **Qo'shgan odamlaringiz soni:** {count} ta\n\n"
            f"🎁 *Eslatma:* Har 50 ta odam uchun 10 000 so'm beriladi. "
            f"Aksiya chekini yoki skrinshotni lichkada adminga yuboring!")
    await message.reply(text, parse_mode='HTML')

@dp.message_handler(content_types=types.ContentTypes.PHOTO, chat_type=types.ChatType.PRIVATE)
async def handle_screenshot(message: types.Message):
    user = message.from_user
    cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    count = row[0] if row else 0
    
    caption_text = (f"🔔 **Yangi ariza (Aksiya)!**\n\n"
                    f"👤 **Ismi:** {user.full_name}\n"
                    f"🔗 **Profili:** @{user.username if user.username else 'Mavjud emas'}\n"
                    f"🆔 **ID:** `{user.id}`\n"
                    f"📊 **Tizimdagi referallari soni:** {count} ta\n"
                    f"💬 **Foydalanuvchi izohi:** {message.caption if message.caption else 'Izoh qoldirilmagan'}")
    
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=caption_text, parse_mode='Markdown')
    await message.reply("✅ Skrinshot va ma'lumotlaringiz adminga muvaffaqiyatli yuborildi!")

@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member_handler(message: types.Message):
    inviter = message.from_user
    new_members = message.new_chat_members
    if inviter.id not in [member.id for member in new_members]:
        added_count = len(new_members)
        cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (inviter.id,))
        row = cursor.fetchone()
        if row:
            new_count = row[0] + added_count
            cursor.execute("UPDATE users SET invited_count = ? WHERE user_id = ?", (new_count, inviter.id))
        else:
            cursor.execute("INSERT INTO users (user_id, username, full_name, invited_count) VALUES (?, ?, ?, ?)",
                           (inviter.id, inviter.username, inviter.full_name, added_count))
        conn.commit()

# 4. RENDER PORT BINDING UCHUN SOXTA VEB SERVER
async def handle_web(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render beradigan dinamik portni o'qib olamiz
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    # Veb server va bot pollingni bir vaqtda ishga tushiramiz
    await start_web_server()
    logging.info("Fake web server started for Render Port Binding.")
    
    # Aiogram botni yurgizamiz
    dispatcher = dp
    try:
        await dispatcher.start_polling()
    finally:
        await dispatcher.storage.close()
        await dispatcher.storage.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())

import logging
import os
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 1. BOT SOZLAMALARI
API_TOKEN = '8645108254:AAG2xvLWF8AaNS4m7-mMK9yDo4gnIKP8GDY'  
ADMIN_ID = 6985111317  

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 2. MA'LUMOTLAR BAZASI (Karta va taklif qilinganlarni bog'lash tizimi)
conn = sqlite3.connect('jomboy_elonlari.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    invited_count INTEGER DEFAULT 0,
    card_number TEXT DEFAULT 'Kiritilmagan'
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS invites (
    invited_id INTEGER PRIMARY KEY,
    inviter_id INTEGER
)
''')
conn.commit()

# 3. START BUYRUG'I VA KARTA QABUL QILISH
@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def start_cmd(message: types.Message):
    await message.reply("👋 Assalomu alaykum! 'Jomboy Elonlari' guruhining rasmiy botiga xush kelibsiz.\n\n"
                        "💳 Aksiyada qatnashish va pulni qabul qilish uchun, iltimos, menga **plastik karta raqamingizni** yuboring (Masalan: `8600123412341234`).")

@dp.message_handler(chat_type=types.ChatType.PRIVATE)
async def get_card_number(message: types.Message):
    text = message.text.replace(" ", "").replace("-", "")
    
    # Karta raqami formatini tekshirish (uzunligi 16 ta raqam bo'lsa)
    if text.isdigit() and len(text) == 16:
        cursor.execute("UPDATE users SET card_number = ? WHERE user_id = ?", (text, message.from_user.id))
        conn.commit()
        await message.reply(f"✅ Karta raqamingiz muvaffaqiyatli saqlandi: `{text}`\n\n"
                            f"📊 Endi guruhga odam qo'shishni boshlashingiz mumkin. Har kuni soat 22:00 da 50 tadan oshgan faol a'zolaringiz uchun pul o'tkazib beriladi.")
    else:
        await message.reply("❌ Xato karta raqami! Iltimos, 16 xonali plastik karta raqamingizni faqat raqamlar bilan yuboring.")

# 4. GURUH ICHIDA STATISTIKANI TEKSHIRISH
@dp.message_handler(commands=['mening_profilim'])
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count, card_number FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    count = row[0] if row else 0
    card = row[1] if row else "Kiritilmagan"
    
    text = (f"👤 **Foydalanuvchi:** {message.from_user.get_mention(as_html=True)}\n"
            f"📊 **Hozirda guruhdagi faol odamlaringiz soni:** {count} ta\n"
            f"💳 **Siz ro'yxatdan o'tkazgan karta:** `{card}`\n\n"
            f"🎁 *Eslatma:* Agar kartangiz kiritilmagan bo'lsa, botning lichkasiga o'tib karta raqamingizni yozib qo'ying!")
    await message.reply(text, parse_mode='HTML')

# 5. GURUHGA ODAM QO'SHILGANDA HISOBLASH (Avtomat tizim)
@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member_handler(message: types.Message):
    inviter = message.from_user
    new_members = message.new_chat_members
    
    if inviter.id not in [member.id for member in new_members]:
        added_count = len(new_members)
        
        # Taklif qiluvchi foydalanuvchini tekshiramiz yoki yaratamiz
        cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (inviter.id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (user_id, username, full_name, invited_count) VALUES (?, ?, ?, ?)",
                           (inviter.id, inviter.username, inviter.full_name, 0))
        
        # Har bir yangi qo'shilgan odamni taklif qiluvchi ID bilan bog'lab bazaga yozamiz
        for member in new_members:
            try:
                cursor.execute("INSERT INTO invites (invited_id, inviter_id) VALUES (?, ?)", (member.id, inviter.id))
                cursor.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (inviter.id,))
            except sqlite3.IntegrityError:
                pass  # Agar bu odam oldin ham qo'shilgan bo'lsa hisoblamaydi
        conn.commit()
    
    try:
        await message.delete()
    except:
        pass

# 6. ODAM GURUHIDAN CHIQIB KETGANDA BALANSDAN AYIRISH (Minus qilish tizimi)
@dp.message_handler(content_types=types.ContentTypes.LEFT_CHAT_MEMBER)
async def left_member_handler(message: types.Message):
    left_user_id = message.left_chat_member.id
    
    # Chiqib ketgan odamni kim guruhga qo'shganini qidiramiz
    cursor.execute("SELECT inviter_id FROM invites WHERE invited_id = ?", (left_user_id,))
    row = cursor.fetchone()
    
    if row:
        inviter_id = row[0]
        # O'sha taklif qiluvchining balansidan -1 ta odam ayiramiz
        cursor.execute("UPDATE users SET invited_count = invited_count - 1 WHERE user_id = ? AND invited_count > 0", (inviter_id,))
        cursor.execute("DELETE FROM invites WHERE invited_id = ?", (left_user_id,))
        conn.commit()
        
    try:
        await message.delete()
    except:
        pass

# 7. HAR KUNI SOAT 22:00 DA ADMIN GA HISOBOT YUBORISH FUNKSIYASI
async def send_daily_report():
    # Faol odamlari soni 50 ta va undan ko'p bo'lganlarni bazadan qidiramiz
    cursor.execute("SELECT user_id, full_name, username, invited_count, card_number FROM users WHERE invited_count >= 50")
    winners = cursor.fetchall()
    
    if winners:
        report_text = "💰 **BUGUNGI AKSIYA G'OLIBLARI RO'YXATI (Soat 22:00 holatiga):**\n\n"
        for user_id, name, username, count, card in winners:
            user_mention = f"[{name}](tg://user?id={user_id})"
            user_user = f" (@{username})" if username else ""
            report_text += f"👤 **G'olib:** {user_mention}{user_user}\n📊 **Haqiqiy odamlari:** {count} ta\n💳 **Karta raqami:** `{card}`\n\n"
            
            # To'lov qilingandan keyin ertasi kuni yana yangidan hisoblashi uchun ularning balansini nollab qo'yamiz (ixtiyoriy)
            cursor.execute("UPDATE users SET invited_count = invited_count - 50 WHERE user_id = ?", (user_id,))
        conn.commit()
        report_text += "📌 *Eslatma: Ro'yxatdagi g'oliblarga pul o'tkazilgach, chekini guruhga ishonch uchun tashlashingiz mumkin.*"
    else:
        report_text = "📅 **Bugun guruhda 50 tadan ko'p faol odam qo'shgan g'oliblar topilmadi.**"
        
    await bot.send_message(chat_id=ADMIN_ID, text=report_text, parse_mode='Markdown')

# 8. RENDER PORT BINDING UCHUN SOXTA VEB SERVER
async def handle_web(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()
    
    # Avtomat taymerni (Apscheduler) sozlash va har kuni 22:00 ga o'rnatish
    scheduler = AsyncIOScheduler(timezone="Asia/Samarkand")
    scheduler.add_job(send_daily_report, 'cron', hour=22, minute=0)
    scheduler.start()
    logging.info("Taymer muvaffaqiyatli yoqildi va soat 22:00 ga sozlandi.")
    
    try:
        await dp.start_polling()
    finally:
        await dp.storage.close()
        await dp.storage.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())

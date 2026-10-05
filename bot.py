import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import sqlite3

# 1. BOT SOZLAMALARI
API_TOKEN = '8645108254:AAG2xvLWF8AaNS4m7-mMK9yDo4gnIKP8GDY'  # Botingizning faol tokeni
ADMIN_ID = 6985111317  # Sizning shaxsiy Telegram ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 2. MA'LUMOTLAR BAZASINI YARATISH (SQLite)
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

# 3. GURUHDA ODAM QO'SHILGANINI ANIKLASH VA HISOBLASH
@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member_handler(message: types.Message):
    inviter = message.from_user  # Odam qo'shgan foydalanuvchi
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

# 4. GURUH ICHIDA STATISTIKANI TEKSHIRISH BUYRUG'I
@dp.message_handler(commands=['mening_profilim'])
async def check_stats(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    count = row[0] if row else 0
    
    text = (f"👤 **Foydalanuvchi:** {message.from_user.get_mention(as_html=True)}\n"
            f"📊 **Qo'shgan odamlaringiz soni:** {count} ta\n\n"
            f"🎁 *Eslatma:* Har 50 ta odam uchun 10 000 so'm beriladi. "
            f"Lichkada botga o'tib, tasdiqlovchi skrinshotni yuboring!")
    await message.reply(text, parse_mode='HTML')

# 5. LICHKADA SKRINSHUT VA KARTA MA'LUMOTLARINI QABUL QILISH
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
    await message.reply("✅ Skrinshot va ma'lumotlaringiz adminga muvaffaqiyatli yuborildi! "
                        "Tez orada tekshirilib, pulingiz o'tkazib beriladi.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

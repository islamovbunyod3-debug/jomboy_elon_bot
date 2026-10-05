import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text

# 1. BOT SOZLAMALARI (HECH QANDAY SOZLAMASIZ TO'G'RIDAN-TO'G'RI ISHLAYDI)
API_TOKEN = '8645108254:AAG2xvLWF8AaNS4m7-mMK9yDo4gnIKP8GDY'
ADMIN_ID = 6985111317  

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
    invited_count INTEGER DEFAULT 0,
    left_count INTEGER DEFAULT 0,
    payment_type TEXT DEFAULT 'Tanlanmagan',
    wallet_info TEXT DEFAULT 'Kiritilmagan'
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS invites (
    invited_id INTEGER PRIMARY KEY,
    inviter_id INTEGER
)
''')
conn.commit()

# 3. MENYU TUGMALARI
def get_main_menu(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Mening profilim"), types.KeyboardButton("To'lov turini sozlash"))
    keyboard.add(types.KeyboardButton("Aksiya qoidalari"))
    if user_id == ADMIN_ID:
        keyboard.add(types.KeyboardButton("Admin paneli"))
    return keyboard

def get_payment_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("Plastik karta", callback_data="pay_card"),
        types.InlineKeyboardButton("Telefon (Paynet)", callback_data="pay_phone")
    )
    return keyboard

# 4. LICHKADA START BUYRUG'I
@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                       (user_id, message.from_user.username, message.from_user.full_name))
        conn.commit()
        
    await message.reply("👋 **Assalomu alaykum!**\n'Jomboy Elonlari' guruhining rasmiy aksiyalar botiga xush kelibsiz.\n\nOdam qo'shib pul ishlashni boshlash uchun pastdagi tugmalardan foydalaning.", 
                        reply_markup=get_main_menu(user_id), parse_mode='Markdown')

# 5. MENING PROFILIM FUNKSIYASI
@dp.message_handler(Text(equals="Mening profilim"))
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count, left_count, payment_type, wallet_info FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    invited, left, pay_type, wallet = row if row else (0, 0, 'Tanlanmagan', 'Kiritilmagan')
    earned_money = (invited // 50) * 10000
    
    text = (f"👤 **Foydalanuvchi:** {message.from_user.get_mention(as_html=True)}\n"
            f"🆔 **ID:** `{user_id}`\n\n"
            f"➕ **Qo'shgan odamlaringiz:** {invited + left} ta\n"
            f"➖ **Guruhdan chiqib ketganlar:** {left} ta\n"
            f"✅ **Hozirgi faol referallaringiz:** {invited} ta\n\n"
            f"💰 **Siz ishlagan pul:** {earned_money:,} so'm\n"
            f"⚙️ **To'lov uslubi:** {pay_type}\n"
            f"📥 **Hamyon/Raqam:** `{wallet}`\n\n"
            f"📌 *Eslatma:* Hamyon kiritish uchun 'To'lov turini sozlash' tugmasini bosing!")
    await message.reply(text, parse_mode='HTML', reply_markup=get_main_menu(user_id))

# 6. TO'LOV TURINI SOZLASH
@dp.message_handler(Text(equals="To'lov turini sozlash"))
async def choose_payment(message: types.Message):
    await message.reply("Pul mukofotini qaysi uslubda qabul qilmoqchisiz? Tanlang 👇", reply_markup=get_payment_menu())

@dp.callback_query_handler(Text(startswith="pay_"))
async def payment_callback(call: types.CallbackQuery):
    action = call.data.split("_")[1]
    if action == "card":
        cursor.execute("UPDATE users SET payment_type = 'Plastik karta' WHERE user_id = ?", (call.from_user.id,))
        await call.message.answer("Menga 16 xonali plastik karta raqamingizni yuboring:")
    elif action == "phone":
        cursor.execute("UPDATE users SET payment_type = 'Telefon (Paynet)' WHERE user_id = ?", (call.from_user.id,))
        await call.message.answer("Menga pul tushadigan telefon raqamingizni yuboring (Masalan: +998991234567):")
    conn.commit()
    await call.answer()

# HITYOT RAQAMLARINI SAQLASH
@dp.message_handler(chat_type=types.ChatType.PRIVATE)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip().replace(" ", "").replace("-", "")
    
    if message.text in ["Mening profilim", "To'lov turini sozlash", "Aksiya qoidalari", "Admin paneli"]:
        return

    cursor.execute("SELECT payment_type FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    pay_type = row[0] if row else "Tanlanmagan"
    
    if pay_type == "Plastik karta":
        if text.isdigit() and len(text) == 16:
            cursor.execute("UPDATE users SET wallet_info = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            await message.reply(f"✅ Karta raqamingiz saqlandi: `{text}`")
        else:
            await message.reply("❌ Xato karta! Iltimos, 16 xonali raqam yuboring.")
    elif pay_type == "Telefon (Paynet)":
        if (text.startswith("+") and text[1:].isdigit() and len(text) == 13) or (text.isdigit() and len(text) == 9):
            cursor.execute("UPDATE users SET wallet_info = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            await message.reply(f"✅ Telefon raqamingiz saqlandi: `{text}`")
        else:
            await message.reply("❌ Xato raqam! Format: `+998991234567`")
    else:
        await message.reply("⚙️ Birinchi navbatda 'To'lov turini sozlash' tugmasini bosing.")

# 7. AKSIYA QOIDALARI
@dp.message_handler(Text(equals="Aksiya qoidalari"))
async def show_rules(message: types.Message):
    rules = ("🔥 **'Jomboy Elonlari' guruhini rivojlantirish aksiyasi!**\n\n"
             "1️⃣ Guruhimizga odam qo'shing.\n"
             "2️⃣ Bot ichida **'Mening profilim'** tugmasini bosib hisobingizni kuzating.\n"
             "3️⃣ Guruhda qolgan har **50 ta faol odam** uchun **10 000 so'm** beriladi.\n"
             "4️⃣ Odamlar guruhdan chiqsa, balansingizdan avtomat kamayadi.\n"
             "5️⃣ Pullar har kuni kechqurun admin tomonidan o'tkazib beriladi.")
    await message.reply(rules, parse_mode='Markdown')

# 8. GURUHDA ODAM HISOBLASH
@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member_handler(message: types.Message):
    inviter = message.from_user
    for member in message.new_chat_members:
        if inviter.id != member.id:
            cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (inviter.id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (inviter.id, inviter.username, inviter.full_name))
            try:
                cursor.execute("INSERT INTO invites (invited_id, inviter_id) VALUES (?, ?)", (member.id, inviter.id))
                cursor.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (inviter.id,))
            except sqlite3.IntegrityError:
                pass
    conn.commit()
    try:
        await message.delete()
    except:
        pass

# ODAM CHIQIB KETGANDA AYIRISH
@dp.message_handler(content_types=types.ContentTypes.LEFT_CHAT_MEMBER)
async def left_member_handler(message: types.Message):
    left_id = message.left_chat_member.id
    cursor.execute("SELECT inviter_id FROM invites WHERE invited_id = ?", (left_id,))
    row = cursor.fetchone()
    if row:
        inviter_id = row[0]
        cursor.execute("UPDATE users SET invited_count = invited_count - 1, left_count = left_count + 1 WHERE user_id = ? AND invited_count > 0", (inviter_id,))
        cursor.execute("DELETE FROM invites WHERE invited_id = ?", (left_id,))
        conn.commit()
    try:
        await message.delete()
    except:
        pass

# 9. ADMIN PANELI (HISOBOT BUYRUG'I)
@dp.message_handler(Text(equals="Admin paneli"))
async def admin_panel_text(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id, full_name, username, invited_count, payment_type, wallet_info FROM users WHERE invited_count >= 50")
    winners = cursor.fetchall()
    if winners:
        report_text = "💰 **BUGUNGI AKSIYA G'OLIBLARI RO'YXATI:**\n\n"
        for user_id, name, username, count, pay_type, wallet in winners:
            money = (count // 50) * 10000
            report_text += f"👤 **G'olib:** {name} (@{username if username else 'yoq'})\n📊 **Odamlari:** {count} ta\n💸 **Pul:** {money:,} so'm\n⚙️ **Uslub:** {pay_type}\n💳 **Hamyon:** `{wallet}`\n\n"
            cursor.execute("UPDATE users SET invited_count = invited_count - 50 WHERE user_id = ?", (user_id,))
        conn.commit()
    else:
        report_text = "📅 **Hozircha bazada 50 tadan ko'p odam qo'shgan g'oliblar mavjud emas.**"
    await message.reply(report_text, parse_mode='Markdown')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

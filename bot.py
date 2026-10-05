import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from aiohttp import web
import asyncio

# 1. BOT SOZLAMALARI
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

# 3. KLAVIATURA TUGMALARI (MENYU)
def get_main_menu(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_profile = types.KeyboardButton("Mening profilim")
    btn_payment = types.KeyboardButton("To'lov turini sozlash")
    btn_rules = types.KeyboardButton("Aksiya qoidalari")
    keyboard.add(btn_profile, btn_payment)
    keyboard.add(btn_rules)
    if user_id == ADMIN_ID:
        btn_admin = types.KeyboardButton("Admin paneli")
        keyboard.add(btn_admin)
    return keyboard

def get_payment_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_card = types.InlineKeyboardButton("Plastik karta", callback_data="pay_card")
    btn_phone = types.InlineKeyboardButton("Telefon (Paynet)", callback_data="pay_phone")
    keyboard.add(btn_card, btn_phone)
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
        
    await message.reply(f"👋 **Assalomu alaykum, {message.from_user.full_name}!**\n'Jomboy Elonlari' guruhining rasmiy aksiyalar botiga xush kelibsiz.\n\n"
                        f"Odam qo'shib pul ishlashni boshlash uchun quyidagi menyu tugmalaridan foydalaning.", 
                        reply_markup=get_main_menu(user_id), parse_mode='Markdown')

# 5. MENING PROFILIM FUNKSIYASI
@dp.message_handler(Text(equals="Mening profilim"))
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count, left_count, payment_type, wallet_info FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        invited, left, pay_type, wallet = row
    else:
        invited, left, pay_type, wallet = 0, 0, 'Tanlanmagan', 'Kiritilmagan'
        
    current_active = invited
    earned_money = (current_active // 50) * 10000
    
    text = (f"👤 **Foydalanuvchi:** {message.from_user.get_mention(as_html=True)}\n"
            f"🆔 **Sizning ID:** `{user_id}`\n\n"
            f"➕ **Jami qo'shgan odamlaringiz:** {invited + left} ta\n"
            f"➖ **Guruhdan chiqib ketganlar:** {left} ta\n"
            f"✅ **Hozirgi faol referallaringiz:** {current_active} ta\n\n"
            f"💰 **Siz ishlagan sof pul:** {earned_money:,} so'm\n"
            f"⚙️ **To'lov uslubi:** {pay_type}\n"
            f"📥 **Hamyon/Raqam:** `{wallet}`\n\n"
            f"📌 *Eslatma:* Agar to'lov hamyoni kiritilmagan bo'lsa, 'To'lov turini sozlash' tugmasini bosing!")
    await message.reply(text, parse_mode='HTML', reply_markup=get_main_menu(user_id))

# 6. TO'LOV TURINI SOZLASH (KARTA YOKI PAYNET)
@dp.message_handler(Text(equals="To'lov turini sozlash"))
async def choose_payment(message: types.Message):
    await message.reply("Pul mukofotini qaysi uslubda qabul qilmoqchisiz? Tanlang 👇", reply_markup=get_payment_menu())

@dp.callback_query_handler(Text(startswith="pay_"))
async def payment_callback(call: types.CallbackQuery):
    action = call.data.split("_")
    if action[1] == "card":
        cursor.execute("UPDATE users SET payment_type = 'Plastik karta' WHERE user_id = ?", (call.from_user.id,))
        await call.message.answer("Menga 16 xonali plastik karta raqamingizni yuboring (Masalan: 8600123412341234):")
    elif action[1] == "phone":
        cursor.execute("UPDATE users SET payment_type = 'Telefon (Paynet)' WHERE user_id = ?", (call.from_user.id,))
        await call.message.answer("Menga pul tushadigan telefon raqamingizni yuboring (Masalan: +998991234567):")
    conn.commit()
    await call.answer()

# FOYDALANUVCHIDAN KARTA YOKI TELEFON RAQAM MATNINI QABUL QILISH
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
            await message.reply(f"✅ Karta raqamingiz muvaffaqiyatli saqlandi: `{text}`")
        else:
            await message.reply("❌ Xato karta raqami! Iltimos, 16 xonali raqam yuboring.")
            
    elif pay_type == "Telefon (Paynet)":
        if (text.startswith("+") and text[1:].isdigit() and len(text) == 13) or (text.isdigit() and len(text) == 9):
            cursor.execute("UPDATE users SET wallet_info = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            await message.reply(f"✅ Telefon raqamingiz Paynet uchun saqlandi: `{text}`")
        else:
            await message.reply("❌ Xato telefon raqami! Iltimos, formatni tekshiring: `+998991234567`")
    else:
        await message.reply("⚙️ Iltimos, birinchi navbatda 'To'lov turini sozlash' tugmasini bosing.")

# 7. AKSIYA QOIDALARI TUGMASI
@dp.message_handler(Text(equals="Aksiya qoidalari"))
async def show_rules(message: types.Message):
    rules = ("🔥 **'Jomboy Elonlari' guruhini rivojlantirish aksiyasi!**\n\n"
             "1️⃣ Guruhimizga odam (kontakt) qo'shing.\n"
             "2️⃣ Bot ichida **'Mening profilim'** tugmasini bosib hisobingizni kuzatib boring.\n"
             "3️⃣ Guruhda qolgan har **50 ta faol odam** uchun **10 000 so'm** pul beriladi.\n"
             "4️⃣ Agar qo'shgan odamlaringiz guruhdan chiqib ketsa, balansingizdan avtomat kamayadi (aldovlar o'tmaydi).\n"
             "5️⃣ Pullar har kuni kechqurun admin tomonidan kartangizga yoki paynet orqali o'tkazib beriladi.")
    await message.reply(rules, parse_mode='Markdown')

# 8. KOP ODAM QOSHGANLARNI HISOBLASH (GURUHDA)
@dp.message_handler(content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
async def new_member_handler(message: types.Message):
    inviter = message.from_user
    new_members = message.new_chat_members
    
    if inviter.id not in [member.id for member in new_members]:
        added_count = len(new_members)
        cursor.execute("SELECT invited_count FROM users WHERE user_id = ?", (inviter.id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                           (inviter.id, inviter.username, inviter.full_name))
        
        for member in new_members:
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

# ODAM CHIQIB KETGANDA HISOBLASH (MINUS QILISH)
@dp.message_handler(content_types=types.ContentTypes.LEFT_CHAT_MEMBER)
async def left_member_handler(message: types.Message):
    left_user_id = message.left_chat_member.id
    cursor.execute("SELECT inviter_id FROM invites WHERE invited_id = ?", (left_user_id,))
    row = cursor.fetchone()
    
    if row:
        inviter_id = row[0]
        cursor.execute("UPDATE users SET invited_count = invited_count - 1, left_count = left_count + 1 WHERE user_id = ? AND invited_count > 0", (inviter_id,))
        cursor.execute("DELETE FROM invites WHERE invited_id = ?", (left_user_id,))
        conn.commit()
    try:
        await message.delete()
    except:
        pass

# 9. GURUH ICHIDA BUYRUQNI QO'LLAB-QUVVATLASH
@dp.message_handler(commands=['mening_profilim'], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_profile(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT invited_count, left_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    invited = row[0] if row else 0
    left = row[1] if row else 0
    
    await message.reply(f"👤 {message.from_user.get_mention(as_html=True)}\n"
                        f"✅ Guruhda qolgan faol referallaringiz: **{invited}** ta\n"
                        f"❌ Chiqib ketganlar: **{left}** ta\n"
                        f"💰 Pul olish uchun bot lichkasiga o'tib hamyoningizni sozlang: @jomboy_elon_bot", parse_mode='HTML')

# 10. FAQQAT SIZ UCHUN: ADMIN PANELI TUGMASI (HISOBOT)
@dp.message_handler(Text(equals="Admin paneli"))
async def admin_panel(message: types.Message):

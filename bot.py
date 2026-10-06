import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

# SOZLAMALAR
BOT_TOKEN = "8645108254:AAFqT2Iufjevzw22-MVQhBHEehBVZYvnXsg"
ADMIN_ID = 6985111317
GROUP_CHAT_ID = -1001826354782

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class PaymentState(StatesGroup):
    waiting_for_card = State()
    waiting_for_phone = State()

# ----------------- MA'LUMOTLAR BAZASI TIZIMI -----------------
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            invited_count INTEGER DEFAULT 0,
            payment_type TEXT DEFAULT NULL,
            payment_details TEXT DEFAULT NULL,
            has_pending_request INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            amount INTEGER,
            payment_type TEXT,
            payment_details TEXT,
            status TEXT DEFAULT 'Kutilmoqda'
        )
    """)
    conn.commit()
    conn.close()

def add_invite(user_id: int, username: str, full_name: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, full_name, invited_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET invited_count = invited_count + 1
    """, (user_id, username, full_name))
    conn.commit()
    conn.close()

def get_user_stats(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT invited_count, payment_type, payment_details, has_pending_request FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, None, None, 0)

def update_payment_details(user_id: int, p_type: str, details: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET payment_type = ?, payment_details = ?, has_pending_request = 1 WHERE user_id = ?", (p_type, details, user_id))
    conn.commit()
    conn.close()

def transfer_to_payouts_and_clear():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, invited_count, payment_type, payment_details FROM users WHERE has_pending_request = 1 AND payment_details IS NOT NULL")
    winners = cursor.fetchall()
    
    for user_id, full_name, count, p_type, p_details in winners:
        payout_blocks = count // 50
        amount = payout_blocks * 10000
        used_invites = payout_blocks * 50
        
        cursor.execute("""
            INSERT INTO payouts (user_id, full_name, amount, payment_type, payment_details)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, full_name, amount, p_type, p_details))
        
        cursor.execute("""
            UPDATE users 
            SET invited_count = invited_count - ?, 
                payment_type = NULL, 
                payment_details = NULL, 
                has_pending_request = 0 
            WHERE user_id = ?
        """, (used_invites, user_id))
        
    conn.commit()
    conn.close()
    return winners

def get_pending_payouts():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, amount, payment_type, payment_details FROM payouts WHERE status = 'Kutilmoqda'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def complete_payout(payout_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount FROM payouts WHERE id = ?", (payout_id,))
    res = cursor.fetchone()
    if res:
        cursor.execute("UPDATE payouts SET status = 'Toʻlandi' WHERE id = ?", (payout_id,))
        conn.commit()
        conn.close()
        return res
    conn.close()
    return None

# ----------------- UYGHOTUVCHI WEB SERVER -----------------
async def handle(request):
    return web.Response(text="Bot is Live!")

app = web.Application()
app.router.add_get('/', handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# ----------------- BOT LOGIKASI VA MENYULARI -----------------
def main_menu_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="📊 Shaxsiy statistika"), KeyboardButton(text="💰 Pulni yechib olish")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👨‍💻 Admin Panel (Toʻlovlar)")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome = (
        "👋 **Xush kelibsiz!**\n\n"
        "📢 **Aksiya sharti:** Guruhimizga kamida **50 ta faol odam** qo'shing va **10 000 so'm** mukofot puliga ega bo'ling!\n\n"
        "Menyu yordamida o'z ballaringizni tekshirishingiz yoki pulni yechib olishga so'rov berishingiz mumkin."
    )
    await message.answer(welcome, reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="Markdown")

@dp.message(F.new_chat_members)
async def tracking_invites(message: types.Message):
    inviter = message.from_user
    try:
        await message.delete()
    except Exception: pass

    for member in message.new_chat_members:
        if member.is_bot or member.id == inviter.id:
            continue
        add_invite(user_id=inviter.id, username=inviter.username or "Foydalanuvchi", full_name=inviter.full_name)

@dp.message(F.left_chat_member)
async def delete_leave_notification(message: types.Message):
    try:
        await message.delete()
    except Exception: pass

@dp.message(F.text == "📊 Shaxsiy statistika")
async def show_stats(message: types.Message):
    count, p_type, p_details, pending = get_user_stats(message.from_user.id)
    earned_money = (count // 50) * 10000
    status_text = (
        f"👤 **Foydalanuvchi:** {message.from_user.full_name}\n"
        f"👥 **Siz qo'shgan umumiy odamlar:** {count} ta\n"
        f"💵 **Yechish mumkin bo'lgan mablag':** {earned_money:,} so'm\n\n"
    )
    if pending == 1:
        status_text += f"⏳ **To'lov holati:** Rekvizit yuborilgan, admin tasdiqlashi kutilmoqda ({p_details})"
    else:
        status_text += f"💳 **Rekvizit:** {p_details if p_details else 'Kiritilmagan'}"
    await message.answer(status_text, parse_mode="Markdown")

@dp.message(F.text == "💰 Pulni yechib olish")
async def withdraw_money(message: types.Message):
    count, _, _, pending = get_user_stats(message.from_user.id)
    if pending == 1:
        await message.answer("⚠️ **Siz allaqachon ariza bergansiz.**\nArizangiz soat 22:00 da adminga ko'rib chiqish uchun yuboriladi.")
        return
    if count < 50:
        await message.answer(f"❌ **Mablag' yechish uchun odam yetarli emas.**\nSizda {count} ta odam bor. Kamida **50 ta** bo'lishi shart.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqamiga", callback_data="pay_card")],
        [InlineKeyboardButton(text="📱 Telefon raqamiga", callback_data="pay_phone")]
    ])
    await message.answer("Pulni qaysi usulda qabul qilmoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data == "pay_card")
async def pay_card(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💳 Karta raqamingiz va Ism-familiyangizni kiriting:")
    await state.set_state(PaymentState.waiting_for_card)
    await callback.answer()

@dp.callback_query(F.data == "pay_phone")
async def pay_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📱 Telefon raqamingizni kiriting (+998xxxxxxx):")
    await state.set_state(PaymentState.waiting_for_phone)
    await callback.answer()

@dp.message(PaymentState.waiting_for_card)
async def proc_card(message: types.Message, state: FSMContext):
    update_payment_details(message.from_user.id, "Karta", message.text)
    await message.answer("✅ To'lov so'rovingiz qabul qilindi! Arizangiz bugun soat 22:00 da adminga ko'rib chiqish uchun yuboriladi.", reply_markup=main_menu_keyboard(message.from_user.id))
    await state.clear()

@dp.message(PaymentState.waiting_for_phone)
async def proc_phone(message: types.Message, state: FSMContext):
    update_payment_details(message.from_user.id, "Tel raqam", message.text)
    await message.answer("✅ To'lov so'rovingiz qabul qilindi! Arizangiz bugun soat 22:00 da adminga ko'rib chiqish uchun yuboriladi.", reply_markup=main_menu_keyboard(message.from_user.id))
    await state.clear()

@dp.message(F.text == "👨‍💻 Admin Panel (Toʻlovlar)")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    pending_list = get_pending_payouts()
    if not pending_list:
        await message.answer("🎉 Hozircha kutilayotgan yangi to'lovlar yo'q.")
        return
        
    await message.answer("📋 **To'lov kutilayotgan g'oliblar ro'yxati:**")
    for p_id, full_name, amount, p_type, p_details in pending_list:
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Toʻlandi va Xabar yuborish", callback_data=f"done_{p_id}")]
        ])
        text = f"👤 **Ism:** {full_name}\n💵 **Summa:** {amount:,} so'm\n🔍 **Tur:** {p_type}\n💳 **Rekvizit:** `{p_details}`"

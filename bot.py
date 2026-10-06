import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web
from database import (init_db, add_invite, get_user_stats, update_payment_details, 
                      transfer_to_payouts_and_clear, get_pending_payouts, complete_payout)

BOT_TOKEN = "8645108254:AAFqT2Iufjevzw22-MVQhBHEehBVZYvnXsg"
ADMIN_ID = 6985111317
GROUP_CHAT_ID = -1001826354782

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class PaymentState(StatesGroup):
    waiting_for_card = State()
    waiting_for_phone = State()

async def handle(request):
    return web.Response(text="Jomboy Elon Bot is Awake and Active!")

app = web.Application()
app.router.add_get('/', handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

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

# 1. GURUHGA KIMDIR ODAM QO'SHGANDA (BALL QO'SHADI VA XABARNI O'CHIRADI)
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

# 2. GURUHGA KIMDIR LINK ORQALI O'ZI KIRGANDA yoki CHIQIB KETGANDA (TIZIM XABARLARINI JAMIY O'CHIRADI)
@dp.message(F.service)
async def delete_all_service_messages(message: types.Message):
    """Guruhdagi har qanday kirdi-chiqdi va xizmat ko'rsatish yozuvlarini shartta o'chiradi"""
    try:
        await message.delete()
    except Exception: pass

# ----------------- QOLGAN FUNKSIYALAR -----------------
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
        await message.answer("⚠️ **Siz allaqachon ariza bergansiz.**\nArizangiz soat 22:00 da adminga yuboriladi va tez orada to'lab beriladi.")
        return
    if count < 50:
        await message.answer(f"❌ **Mablag' yechish uchun odam yetarli emas.**\(\nSizda {count}\) ta odam bor. Kamida **50 ta** bo'lishi shart.")
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

# ----------------- ADMIN PANEL -----------------
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
        await message.answer(text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("done_"))
async def approve_payout(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    payout_id = int(callback.data.split("_"))
    result = complete_payout(payout_id)
    
    if result:
        user_id, amount = result
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"✅ **Xushxabar!**\n\nGuruhga qo'shgan odamlaringiz uchun so'ralgan **{amount:,} so'm** mukofot puli admin tomonidan rekvizitingizga to'liq o'tkazib berildi! Rahmat!"
            )
            await callback.message.edit_text(callback.message.text + "\n\n🟢 **[TO'LANDI: Foydalanuvchiga xabar ketdi]**")
        except Exception:
            await callback.message.edit_text(callback.message.text + "\n\n🟡 **[TO'LANDI: Lekin foydalanuvchi botni bloklagan]**")
    await callback.answer()

async def daily_cron_job():
    winners = transfer_to_payouts_and_clear()
    if winners:
        report = f"🔔 **Soat 22:00 bo'ldi!**\n📈 Bugun jami **{len(winners)} ta** foydalanuvchi pul yechishga so'rov yuborgan. Ularning arizalari Admin Panelga joylandi."
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=report)
        except Exception: pass

async def main():
    init_db()
    await start_web_server()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_cron_job, 'cron', hour=22, minute=0, timezone="Asia/Tashkent")
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

python
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncScheduler
from database import init_db, add_invite, get_user_stats, update_payment_details, get_winners_for_admin, clear_all_data

# SOZLAMALAR
BOT_TOKEN = "7336040854:AAEg..."  # Bot tokeningiz
ADMIN_ID = 123456789            # O'zingizning shaxsiy Telegram ID raqamingiz (Admin)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchidan rekvizitlarni so'rash holatlari (FSM)
class PaymentState(StatesGroup):
    waiting_for_card = State()
    waiting_for_phone = State()

# ASOSIY MENU MATNI VA KNOPKALARI
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Shaxsiy statistika"), KeyboardButton(text="💰 Pulni yechib olish")]
        ],
        resize_keyboard=True
    )

# /start BOSILGANDA
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 **Xush kelibsiz!**\n\n"
        "📢 **Aksiya sharti:** Guruhimizga kamida **50 ta faol odam** qo'shing va **10 000 so'm** mukofot puliga ega bo'ling!\n\n"
        "Menyu yordamida o'z hisobingizni tekshirishingiz yoki to'lov ma'lumotlarini yuborishingiz mumkin."
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

# GURUHGA ODAM QO'SHILGANDA HISOBLASH
@dp.message(F.new_chat_members)
async def tracking_invites(message: types.Message):
    inviter = message.from_user
    for member in message.new_chat_members:
        if member.is_bot or member.id == inviter.id:
            continue
        add_invite(
            user_id=inviter.id,
            username=inviter.username or "Foydalanuvchi",
            full_name=inviter.full_name
        )

# STATISTIKANI TEKSHIRISH
@dp.message(F.text == "📊 Shaxsiy statistika")
async def show_stats(message: types.Message):
    count, p_type, p_details = get_user_stats(message.from_user.id)
    # Har 50 ta odam uchun 10 000 so'm hisoblaymiz (masalan, 100 ta qo'shsa 20 000 so'm)
    earned_money = (count // 50) * 10000
    
    status_text = (
        f"👤 **Foydalanuvchi:** {message.from_user.full_name}\n"
        f"👥 **Qo'shgan odamlaringiz:** {count} ta\n"
        f"💵 **Ishlangan mablag':** {earned_money:,} so'm\n\n"
    )
    if p_details:
        status_text += f"💳 **Kiritilgan rekvizit:** {p_details} ({p_type})"
    else:
        status_text += "⚠️ *To'lov ma'lumotlari hali kiritilmagan.*"
        
    await message.answer(status_text, parse_mode="Markdown")

# PULNI YECHIB OLISH TUGMASI
@dp.message(F.text == "💰 Pulni yechib olish")
async def withdraw_money(message: types.Message):
    count, _, _ = get_user_stats(message.from_user.id)
    
    if count < 50:
        await message.answer(f"❌ **Uzr, mablag' yechish uchun yetarli odam qo'shilmagan.**\nSiz hozircha {count} ta odam qo'shgansiz. Kamida **50 ta** bo'lishi kerak.")
        return

    # To'lov turini tanlash uchun inline tugmalar
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqamiga", callback_data="pay_card")],
        [InlineKeyboardButton(text="📱 Telefon raqamiga", callback_data="pay_phone")]
    ])
    await message.answer("Pulni qaysi usulda qabul qilib olmoqchisiz? Tanlang:", reply_markup=kb)

# CHOOSE KARTA OR PHONE
@dp.callback_query(F.data == "pay_card")
async def pay_card_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💳 Iltimos, **8600...** yoki **9860...** bilan boshlanadigan karta raqamingizni va ism-familiyangizni yozib yuboring:")
    await state.set_state(PaymentState.waiting_for_card)
    await callback.answer()

@dp.callback_query(F.data == "pay_phone")
async def pay_phone_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📱 Iltimos, telefon raqamingizni kiriting (Masalan: +998991234567):")
    await state.set_state(PaymentState.waiting_for_phone)
    await callback.answer()

# REKVIZITLARNI QABUL QILISH
@dp.message(PaymentState.waiting_for_card)
async def process_card(message: types.Message, state: FSMContext):
    update_payment_details(message.from_user.id, "Karta", message.text)
    await message.answer("✅ Karta raqamingiz muvaffaqiyatli saqlandi! Bugun soat 22:00 da adminga yuboriladi.", reply_markup=main_menu_keyboard())
    await state.clear()

@dp.message(PaymentState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    update_payment_details(message.from_user.id, "Tel raqam", message.text)
    await message.answer("✅ Telefon raqamingiz muvaffaqiyatli saqlandi! Bugun soat 22:00 da adminga yuboriladi.", reply_markup=main_menu_keyboard())
    await state.clear()

# HAR KUNI SOAT 22:00 DA ADMINGA HISOBOT YUBORISH
async def send_admin_report():
    winners = get_winners_for_admin()
    if winners:
        report_text = "💰 **Bugungi yutuq egalari ro'yxati (Soat 22:00 holatiga):**\n\n"
        for user_id, username, full_name, count, p_type, p_details in winners:
            money = (count // 50) * 10000
            user_mention = f"@{username}" if username else f"ID: {user_id}"
            report_text += (
                f"👤 **G'olib:** {full_name} ({user_mention})\n"
                f"👥 **Qo'shgan odami:** {count} ta\n"
                f"💵 **To'lanadigan summa:** {money:,} so'm\n"
                f"💳 **Rekvizit ({p_type}):** `{p_details}`\n"
                f"-----------------------------------------\n"
            )
    else:
        report_text = "🤷‍♂️ **Bugun 50 tadan ko'p odam qo'shib, hamyonini kiritgan g'oliblar mavjud emas.**"

    try:
        # Adminga hisobot yuborish
        await bot.send_message(chat_id=ADMIN_ID, text=report_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Adminga hisobot yuborishda xatolik: {e}")

    # TOZALASH: Hisobot ketgach hamma narsani 0 qilamiz
    clear_all_data()
    logging.info("Kun yakunlandi. Barcha kirdi-chiqdilar va rekvizitlar muvaffaqiyatli tozalandi.")

# LOYIHANI ISHGA TUSHIRISH
async main():
    init_db()
    scheduler = AsyncScheduler()
    # Har kuni soat 22:00 da Toshkent vaqti bilan adminga hisobot yuborish scheduler'i
    scheduler.add_job(send_admin_report, 'cron', hour=22, minute=0, timezone="Asia/Tashkent")
    scheduler.start()
    
    logging.info("Bot va Administrator taymeri muvaffaqiyatli yoqildi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

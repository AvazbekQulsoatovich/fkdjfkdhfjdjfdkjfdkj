import asyncio
from aiogram import Router, types, F
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.enums.chat_action import ChatAction
from db import create_pool
from config import ADMIN_ID

router = Router()

# --- Bot yozayotgandek animatsiya ---
async def typing(message: types.Message, delay: float = 1.2):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(delay)


# --- BOSQICH 1: Buyurtmani yakunlash ---
@router.callback_query(F.data == "finish_order")
async def start_order(callback: CallbackQuery):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )
    await callback.message.answer(
        "📱 Buyurtmani yakunlash uchun telefon raqamingizni yuboring:",
        reply_markup=kb
    )
    await callback.answer()


# --- BOSQICH 2: Telefon raqamni olish ---
@router.message(F.contact)
async def get_phone(message: types.Message):
    await typing(message)
    phone = message.contact.phone_number

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO users (telegram_id, phone) 
               VALUES ($1, $2)
               ON CONFLICT (telegram_id) DO UPDATE SET phone=$2''',
            message.from_user.id, phone
        )

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True
    )
    await message.answer("📍 Endi lokatsiyangizni yuboring:", reply_markup=kb)


# --- BOSQICH 3: Lokatsiyani olish ---
@router.message(F.location)
async def get_location(message: types.Message):
    await typing(message)
    lat, lon = message.location.latitude, message.location.longitude
    location = f"{lat},{lon}"

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''UPDATE users SET location=$1 WHERE telegram_id=$2''',
            location, message.from_user.id
        )

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💵 Naqd"), KeyboardButton(text="💳 Karta")]],
        resize_keyboard=True
    )
    await message.answer("💳 To‘lov turini tanlang:", reply_markup=kb)


# --- BOSQICH 4: To‘lov turini tanlash va buyurtmani yakunlash ---
@router.message(F.text.in_(["💵 Naqd", "💳 Karta"]))
async def choose_payment(message: types.Message):
    await typing(message)
    payment_type = message.text

    pool = await create_pool()
    async with pool.acquire() as conn:
        # Savatdagi mahsulotlar
        cart_items = await conn.fetch(
            '''
            SELECT p.id AS product_id, p.name, p.price, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=$1 AND c.status='pending'
            ''',
            message.from_user.id
        )

        if not cart_items:
            await message.answer("❌ Savatingiz bo‘sh.")
            return

        total = sum(float(item['price']) * item['quantity'] for item in cart_items)

        # Buyurtma yaratish
        order_id = await conn.fetchval(
            '''
            INSERT INTO orders (user_id, total_price, payment_type, status)
            VALUES ($1, $2, $3, 'pending')
            RETURNING id
            ''',
            message.from_user.id, total, payment_type
        )

        # Har bir mahsulotni orders_items ga yozish
        for item in cart_items:
            await conn.execute(
                '''
                INSERT INTO orders_items (order_id, product_id, quantity, price)
                VALUES ($1, $2, $3, $4)
                ''',
                order_id, item['product_id'], item['quantity'], item['price']
            )

        # Savatni bo'shatish
        await conn.execute(
            '''DELETE FROM cart WHERE user_id=$1 AND status='pending' ''',
            message.from_user.id
        )

    # --- Foydalanuvchi xabari ---
    if payment_type == "💵 Naqd":
        await message.answer(
            f"✅ Buyurtma #{order_id} qabul qilindi!\n"
            f"💰 Umumiy: {total:.0f} so‘m\n"
            "Admin tez orada bog‘lanadi.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Admin xabari
        await message.bot.send_message(
            ADMIN_ID,
            f"📥 <b>Yangi buyurtma</b> (Naqd)\n"
            f"Buyurtma raqami: #{order_id}\n"
            f"💰 Umumiy: {total:.0f} so‘m\n"
            f"👤 Foydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})",
            parse_mode="HTML"
        )
    else:
        # Karta to‘lovi
        card_number = "<code>8600 1234 5678 9012</code>"
        await message.answer(
            f"💳 Karta orqali to‘lov:\n\n"
            f"To‘lovni ushbu karta raqamiga qiling: {card_number}\n\n"
            f"💰 Umumiy: {total:.0f} so‘m\n\n"
            "To‘lovni tasdiqlash uchun <b>chek rasmini yuboring</b>.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.bot.send_message(
            ADMIN_ID,
            f"📥 <b>Yangi buyurtma</b> (Karta)\n"
            f"Buyurtma raqami: #{order_id}\n"
            f"💰 Umumiy: {total:.0f} so‘m\n"
            f"👤 Foydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\n\n"
            "Foydalanuvchi to‘lov cheki yuborishi kerak.",
            parse_mode="HTML"
        )


# --- BOSQICH 5: Chek rasmini qabul qilish ---
@router.message(F.photo)
async def receive_payment_check(message: types.Message):
    pool = await create_pool()
    async with pool.acquire() as conn:
        order_id = await conn.fetchval(
            '''SELECT id FROM orders 
               WHERE user_id=$1 AND status='pending' 
               ORDER BY id DESC LIMIT 1''',
            message.from_user.id
        )

    if not order_id:
        await message.answer("❌ Sizning faol buyurtmangiz yo‘q.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{order_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{order_id}")
            ]
        ]
    )

    await message.bot.send_photo(
        ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"💳 Chek tasdiqlash uchun buyurtma #{order_id}\n"
                f"👤 {message.from_user.full_name} (ID: {message.from_user.id})",
        reply_markup=kb
    )
    await message.answer("✅ Chek admin tomonidan tekshirilmoqda.")


# --- BOSQICH 6: Admin tasdiqlash ---
@router.callback_query(F.data.startswith("approve_"))
async def approve_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''UPDATE orders SET status='approved' WHERE id=$1''',
            order_id
        )

        user_id = await conn.fetchval(
            '''SELECT user_id FROM orders WHERE id=$1''',
            order_id
        )

    await callback.message.edit_caption(f"✅ Buyurtma #{order_id} tasdiqlandi!")
    await callback.bot.send_message(
        user_id,
        f"✅ To‘lovingiz tasdiqlandi!\nBuyurtma #{order_id} qabul qilindi. 🎉"
    )


# --- BOSQICH 7: Admin bekor qilish ---
@router.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            '''UPDATE orders SET status='rejected' WHERE id=$1''',
            order_id
        )

        user_id = await conn.fetchval(
            '''SELECT user_id FROM orders WHERE id=$1''',
            order_id
        )

    await callback.message.edit_caption(f"❌ Buyurtma #{order_id} bekor qilindi.")
    await callback.bot.send_message(
        user_id,
        f"❌ To‘lov cheki rad etildi.\nBuyurtma #{order_id} bekor qilindi."
    )

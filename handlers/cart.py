from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import create_pool
from config import ADMIN_ID  # Admin ID

router = Router()


# --- Savat matni va tugmalarini generatsiya qilish ---
async def generate_cart_text_and_keyboard(user_id: int):
    pool = await create_pool()
    async with pool.acquire() as conn:
        items = await conn.fetch('''
            SELECT p.id, p.name, p.price, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = $1 AND c.status = 'pending'
        ''', user_id)

    if not items:
        return "🛒 Savatingiz bo‘sh!", None

    text = "🛒 <b>Savatingiz:</b>\n\n"
    total = 0
    keyboard = []

    for item in items:
        summa = float(item['price']) * item['quantity']
        total += summa
        text += f"🍔 <b>{item['name']}</b> x {item['quantity']} = {summa:.0f} so‘m\n"

        # Mahsulot sonini boshqarish tugmalari
        keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec_{item['id']}"),
            InlineKeyboardButton(text=f"{item['quantity']} dona", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{item['id']}")
        ])

    text += f"\n💰 <b>Umumiy:</b> {total:.0f} so‘m"
    text += "\n\n✅ Buyurtmani yakunlash uchun tugmadan foydalaning."

    # Yakunlash va tozalash tugmalari
    keyboard.append([InlineKeyboardButton(text="✅ Buyurtmani yakunlash", callback_data="finish_order")])
    keyboard.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")])

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return text, kb


# --- Savatni ko‘rsatish ---
@router.message(F.text == "🛒 Savat")
async def view_cart(message: types.Message):
    text, kb = await generate_cart_text_and_keyboard(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


# --- Savatga qo‘shish ---
@router.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO cart (user_id, product_id, quantity, status)
            VALUES ($1, $2, 1, 'pending')
            ON CONFLICT (user_id, product_id, status)
            DO UPDATE SET quantity = cart.quantity + 1
        ''', callback.from_user.id, product_id)

    await callback.answer("➕ Savatga qo‘shildi!")


# --- Miqdorni oshirish ---
@router.callback_query(F.data.startswith("inc_"))
async def increment_quantity(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE cart
            SET quantity = quantity + 1
            WHERE user_id = $1 AND product_id = $2 AND status='pending'
        ''', callback.from_user.id, product_id)

    text, kb = await generate_cart_text_and_keyboard(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer("➕ Miqdor oshirildi!")


# --- Miqdorni kamaytirish ---
@router.callback_query(F.data.startswith("dec_"))
async def decrement_quantity(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        quantity = await conn.fetchval('''
            SELECT quantity FROM cart
            WHERE user_id = $1 AND product_id = $2 AND status='pending'
        ''', callback.from_user.id, product_id)

        if quantity and quantity > 1:
            await conn.execute('''
                UPDATE cart
                SET quantity = quantity - 1
                WHERE user_id = $1 AND product_id = $2 AND status='pending'
            ''', callback.from_user.id, product_id)
        else:
            await conn.execute('''
                DELETE FROM cart
                WHERE user_id = $1 AND product_id = $2 AND status='pending'
            ''', callback.from_user.id, product_id)

    text, kb = await generate_cart_text_and_keyboard(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer("➖ Miqdor o‘zgartirildi!")


# --- Savatni tozalash ---
@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM cart WHERE user_id = $1 AND status='pending'
        ''', callback.from_user.id)

    await callback.message.edit_text("🗑 Savatingiz tozalandi!", parse_mode="HTML")
    await callback.answer("✅ Savat bo‘shatildi!")


# --- Buyurtmani yakunlash (To'lov turini tanlash) ---
@router.callback_query(F.data == "finish_order")
async def finish_order(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta orqali to'lash", callback_data="pay_card")],
        [InlineKeyboardButton(text="💵 Naqd to'lash", callback_data="pay_cash")]
    ])
    await callback.message.edit_text(
        "💰 <b>To'lov turini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer("To'lov turini tanlang.")


# --- Karta orqali to'lash ---
@router.callback_query(F.data == "pay_card")
async def pay_by_card(callback: types.CallbackQuery):
    card_number = "<code>8600 1234 5678 9012</code>"
    await callback.message.edit_text(
        f"💳 To'lovni amalga oshirish uchun karta raqami:\n\n{card_number}\n\n"
        "To'lovni tasdiqlash uchun admin kuting.",
        parse_mode="HTML"
    )

    # Admin tasdiqlashi uchun xabar
    await callback.bot.send_message(
        ADMIN_ID,
        f"📥 <b>Yangi buyurtma (Karta to'lovi)</b>\n"
        f"Foydalanuvchi: {callback.from_user.full_name} (ID: {callback.from_user.id})\n"
        "Buyurtma tasdiqlansinmi?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_order_{callback.from_user.id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_order_{callback.from_user.id}")]
        ])
    )
    await callback.answer("Karta to'lovi jarayoni boshlandi.")


# --- Naqd to'lash ---
@router.callback_query(F.data == "pay_cash")
async def pay_by_cash(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💵 Buyurtmangiz naqd to'lov asosida qabul qilindi. Admin tez orada yetkazib beradi.",
        parse_mode="HTML"
    )

    # Admin xabar oladi (tasdiqlash tugmasiz)
    await callback.bot.send_message(
        ADMIN_ID,
        f"📥 <b>Yangi buyurtma (Naqd)</b>\n"
        f"Foydalanuvchi: {callback.from_user.full_name} (ID: {callback.from_user.id})",
        parse_mode="HTML"
    )
    await callback.answer("Naqd to'lov tanlandi.")


# --- Admin tasdiqlash ---
@router.callback_query(F.data.startswith("confirm_order_"))
async def confirm_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await callback.bot.send_message(user_id, "✅ Buyurtmangiz admin tomonidan tasdiqlandi!")
    await callback.answer("Buyurtma tasdiqlandi.")


@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    await callback.bot.send_message(user_id, "❌ Buyurtmangiz admin tomonidan bekor qilindi.")
    await callback.answer("Buyurtma bekor qilindi.")


# --- Ignore tugmasi ---
@router.callback_query(F.data == "ignore")
async def ignore_button(callback: types.CallbackQuery):
    await callback.answer()

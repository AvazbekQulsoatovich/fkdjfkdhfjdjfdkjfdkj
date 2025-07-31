from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from db import create_pool
from config import ADMIN_ID

router = Router()

# --- Admin buyurtmalarni ko‘rish ---
@router.message(lambda msg: msg.text in ["/orders", "📦 Buyurtmalar (Admin)"])
async def show_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu bo‘limga kirish huquqi yo‘q.")
        return

    pool = await create_pool()
    async with pool.acquire() as conn:
        orders = await conn.fetch('''
            SELECT o.id, o.user_id, u.fullname, u.phone, o.total_price, 
                   o.payment_type, o.check_image, o.status, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.status IS NULL OR o.status = 'pending'
            ORDER BY o.created_at DESC
            LIMIT 5
        ''')

    if not orders:
        await message.answer("📦 Hozircha yangi buyurtmalar yo‘q.")
        return

    for o in orders:
        text = (
            f"🆔 <b>ID:</b> {o['id']}\n"
            f"👤 <b>Mijoz:</b> {o['fullname']}\n"
            f"📞 <b>Tel:</b> {o['phone'] or '❌'}\n"
            f"💰 <b>Summa:</b> {o['total_price']} so‘m\n"
            f"💳 <b>To‘lov:</b> {o['payment_type']}\n"
            f"📅 <b>Sana:</b> {o['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{o['id']}")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{o['id']}")]
            ]
        )

        await message.answer(text, parse_mode="HTML", reply_markup=kb)

        # Chek rasmi bo‘lsa, alohida yuboriladi
        if o['check_image']:
            await message.answer_photo(o['check_image'], caption="💳 To‘lov cheki")


# --- Buyurtmani tasdiqlash ---
@router.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    pool = await create_pool()

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT user_id, total_price FROM orders WHERE id=$1", order_id
        )
        if not order:
            await callback.answer("❌ Buyurtma topilmadi.")
            return

        await conn.execute("UPDATE orders SET status='confirmed' WHERE id=$1", order_id)

    await callback.message.edit_text(f"✅ Buyurtma #{order_id} tasdiqlandi!")
    await callback.answer("Tasdiqlandi.")

    try:
        await callback.bot.send_message(
            order["user_id"],
            f"✅ Buyurtmangiz (ID: {order_id}) tasdiqlandi!\n"
            f"💰 Umumiy summa: {order['total_price']} so‘m.\n"
            "Operatorimiz tez orada siz bilan bog‘lanadi."
        )
    except:
        print(f"⚠ Mijozga xabar yuborilmadi. user_id={order['user_id']}")


# --- Buyurtmani bekor qilish ---
@router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    pool = await create_pool()

    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT user_id FROM orders WHERE id=$1", order_id
        )
        if not order:
            await callback.answer("❌ Buyurtma topilmadi.")
            return

        await conn.execute("UPDATE orders SET status='rejected' WHERE id=$1", order_id)

    await callback.message.edit_text(f"❌ Buyurtma #{order_id} bekor qilindi!")
    await callback.answer("Bekor qilindi.")

    try:
        await callback.bot.send_message(
            order["user_id"],
            f"❌ Buyurtmangiz (ID: {order_id}) bekor qilindi.\n"
            "Iltimos, boshqa buyurtma berib ko‘ring yoki operator bilan bog‘laning."
        )
    except:
        print(f"⚠ Mijozga xabar yuborilmadi. user_id={order['user_id']}")


# --- Foydalanuvchi chek rasmini yuboradi ---
@router.message(F.photo)
async def receive_payment_check(message: Message):
    pool = await create_pool()
    async with pool.acquire() as conn:
        order_id = await conn.fetchval('''
            SELECT id FROM orders
            WHERE user_id = $1 AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
        ''', message.from_user.id)

        if not order_id:
            await message.answer("❌ Sizda tasdiqlanmagan buyurtma yo‘q.")
            return

        # Chek rasmini saqlash
        file_id = message.photo[-1].file_id
        await conn.execute('''
            UPDATE orders SET check_image=$1 WHERE id=$2
        ''', file_id, order_id)

    # Foydalanuvchiga xabar
    await message.answer("✅ Chek rasmini qabul qildik. Admin tez orada tekshiradi.")

    # Adminga xabar
    await message.bot.send_message(
        ADMIN_ID,
        f"💳 Yangi chek yuborildi!\n"
        f"📦 Buyurtma ID: {order_id}\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"Telegram ID: {message.from_user.id}"
    )
    await message.bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"💳 Buyurtma #{order_id} uchun chek."
    )

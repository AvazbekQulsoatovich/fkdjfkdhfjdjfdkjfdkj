from aiogram import Router, F
from aiogram.types import Message
from db import create_pool
from config import ADMIN_ID  # ADMIN_ID ni ishlatamiz

router = Router()

# Foydalanuvchi chek rasmini yuboradi
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

    # Adminga xabar yuborish
    await message.bot.send_message(
        ADMIN_ID,
        f"💳 Yangi chek yuborildi!\n"
        f"📦 Buyurtma ID: {order_id}\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"Telegram ID: {message.from_user.id}"
    )

    # Adminga chek rasmini yuborish
    await message.bot.send_photo(
        ADMIN_ID,
        file_id,
        caption=f"💳 Buyurtma #{order_id} uchun chek."
    )

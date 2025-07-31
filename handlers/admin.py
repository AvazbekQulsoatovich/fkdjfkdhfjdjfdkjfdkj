import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_ID
from db import create_pool

router = Router()

# --- ADMIN MENYU ---
async def admin_menu(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Buyurtmalar (Admin)")],
            [KeyboardButton(text="➕ Mahsulot qo‘shish")],
            [KeyboardButton(text="❌ Mahsulotni o‘chirish")],
            [KeyboardButton(text="✏️ Mahsulotni o‘zgartirish")],
            [KeyboardButton(text="🔙 Foydalanuvchi menyusiga qaytish")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 <b>Admin paneliga xush kelibsiz!</b>", parse_mode="HTML", reply_markup=kb)


# --- FOYDALANUVCHI MENYUSI ---
async def user_menu(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍔 Menyu"), KeyboardButton(text="🛒 Savat")],
            [KeyboardButton(text="📦 Buyurtmalarim")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔙 Foydalanuvchi menyusiga qaytdingiz.", reply_markup=kb)


@router.message(Command("admin"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await admin_menu(message)


@router.message(F.text == "🔙 Foydalanuvchi menyusiga qaytish")
async def back_to_user_menu(message: types.Message):
    await user_menu(message)


# =======================
# === MAHSULOT QO‘SHISH ===
# =======================
class AddProduct(StatesGroup):
    name = State()
    price = State()
    image = State()


@router.message(F.text == "➕ Mahsulot qo‘shish")
async def start_add_product(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProduct.name)
    await message.answer("🍔 Yangi mahsulot nomini kiriting:", reply_markup=ReplyKeyboardRemove())


@router.message(AddProduct.name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Mahsulot narxini kiriting (so‘mda):")


@router.message(AddProduct.price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not (message.text and message.text.isdigit()):
        await message.answer("❌ Narx faqat raqamlardan iborat bo‘lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddProduct.image)
    await message.answer("🖼 Mahsulot rasmini yuboring (URL yoki rasm fayli bo‘lishi mumkin):")


@router.message(AddProduct.image)
async def add_product_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pool = await create_pool()

    # Rasmni tekshirish
    if message.photo:
        file = await message.bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"
    elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        image_url = message.text
    else:
        await message.answer("❌ Rasm yoki URL yuboring.")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO products (name, price, image_url)
            VALUES ($1, $2, $3)
            ''',
            data['name'], data['price'], image_url
        )

    await message.answer(f"✅ <b>{data['name']}</b> mahsuloti qo‘shildi!", parse_mode="HTML")
    await state.clear()
    await asyncio.sleep(0.5)
    await admin_menu(message)


# =======================
# === MAHSULOT O‘CHIRISH ===
# =======================
@router.message(F.text == "❌ Mahsulotni o‘chirish")
async def delete_product_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    pool = await create_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT id, name FROM products")

    if not products:
        await message.answer("❌ Mahsulotlar yo‘q.")
        return

    text = "🗑 <b>O‘chirish uchun mahsulot ID raqamini kiriting:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} - {p['name']}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(lambda msg: msg.text and msg.text.isdigit())
async def confirm_delete_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    product_id = int(message.text)
    pool = await create_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)

    if result == "DELETE 0":
        await message.answer("❌ Bunday ID bilan mahsulot topilmadi.")
    else:
        await message.answer(f"✅ ID {product_id} mahsulot o‘chirildi.")

    await admin_menu(message)


# =======================
# === MAHSULOT O‘ZGARTIRISH ===
# =======================
class EditProduct(StatesGroup):
    choose_id = State()
    field = State()
    new_value = State()


@router.message(F.text == "✏️ Mahsulotni o‘zgartirish")
async def edit_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    pool = await create_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT id, name, price FROM products")

    if not products:
        await message.answer("❌ Mahsulotlar yo‘q.")
        return

    text = "✏️ <b>O‘zgartirish uchun mahsulot ID raqamini kiriting:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} - {p['name']} ({p['price']} so‘m)\n"

    await state.set_state(EditProduct.choose_id)
    await message.answer(text, parse_mode="HTML")


@router.message(EditProduct.choose_id)
async def edit_product_field(message: types.Message, state: FSMContext):
    if not (message.text and message.text.isdigit()):
        await message.answer("❌ ID raqami raqam bo‘lishi kerak!")
        return

    product_id = int(message.text)
    pool = await create_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT * FROM products WHERE id=$1", product_id)

    if not product:
        await message.answer("❌ Bunday ID bilan mahsulot topilmadi.")
        await state.clear()
        return

    await state.update_data(product_id=product_id)
    await state.set_state(EditProduct.field)
    await message.answer(
        "Qaysi maydonni o‘zgartirmoqchisiz?\n\n"
        "1️⃣ Nom\n2️⃣ Narx\n3️⃣ Rasm URL\n\n1, 2 yoki 3 kiriting:"
    )


@router.message(EditProduct.field)
async def edit_product_new_value(message: types.Message, state: FSMContext):
    choice = message.text
    if choice not in ["1", "2", "3"]:
        await message.answer("❌ 1, 2 yoki 3 ni tanlang.")
        return

    await state.update_data(field=choice)
    await state.set_state(EditProduct.new_value)

    if choice == "1":
        await message.answer("✏️ Yangi mahsulot nomini kiriting:")
    elif choice == "2":
        await message.answer("✏️ Yangi narxni kiriting (so‘mda):")
    else:
        await message.answer("✏️ Yangi rasm URL manzilini kiriting:")


@router.message(EditProduct.new_value)
async def save_product_changes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data['product_id']
    field = data['field']
    new_value = message.text

    pool = await create_pool()
    async with pool.acquire() as conn:
        if field == "1":
            await conn.execute("UPDATE products SET name=$1 WHERE id=$2", new_value, product_id)
        elif field == "2":
            if not new_value.isdigit():
                await message.answer("❌ Narx faqat raqam bo‘lishi kerak!")
                return
            await conn.execute("UPDATE products SET price=$1 WHERE id=$2", int(new_value), product_id)
        else:
            await conn.execute("UPDATE products SET image_url=$1 WHERE id=$2", new_value, product_id)

    await message.answer("✅ Mahsulot muvaffaqiyatli yangilandi.")
    await state.clear()
    await admin_menu(message)


# =======================
# === BUYURTMALAR ===
# =======================
@router.message(F.text == "📦 Buyurtmalar (Admin)")
async def show_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu bo‘limga kirish huquqi yo‘q.")
        return

    pool = await create_pool()
    async with pool.acquire() as conn:
        orders = await conn.fetch(
            '''
            SELECT o.id, u.fullname, o.total_price, o.payment_type, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.telegram_id
            ORDER BY o.created_at DESC
            LIMIT 5
            '''
        )

    if not orders:
        await message.answer("📦 Hozircha buyurtmalar yo‘q.")
        return

    for o in orders:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton("📖 Tafsilotlar", callback_data=f"order_{o['id']}")]
            ]
        )
        text = (
            f"🆔 <b>ID:</b> {o['id']}\n"
            f"👤 <b>Mijoz:</b> {o['fullname']}\n"
            f"💰 <b>Summa:</b> {o['total_price']} so‘m\n"
            f"💳 <b>To‘lov:</b> {o['payment_type']}\n"
            f"📅 <b>Sana:</b> {o['created_at']}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data.startswith("order_"))
async def order_details(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Ruxsat yo‘q.")
        return

    order_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            '''
            SELECT o.id, u.fullname, u.phone, u.location, o.total_price, o.payment_type, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.id=$1
            ''',
            order_id
        )

        items = await conn.fetch(
            '''
            SELECT p.name, oi.quantity, oi.price
            FROM orders_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id=$1
            ''',
            order_id
        )

    if not order:
        await callback.message.answer("❌ Buyurtma topilmadi.")
        return

    text = (
        f"🆔 <b>ID:</b> {order['id']}\n"
        f"👤 <b>Mijoz:</b> {order['fullname']}\n"
        f"📞 <b>Tel:</b> {order['phone'] or '❌'}\n"
        f"📍 <b>Lokatsiya:</b> {order['location'] or '❌'}\n"
        f"💰 <b>Summa:</b> {order['total_price']} so‘m\n"
        f"💳 <b>To‘lov:</b> {order['payment_type']}\n"
        f"📅 <b>Sana:</b> {order['created_at']}\n\n"
        "📦 <b>Buyurtma tarkibi:</b>\n"
    )

    for item in items:
        summa = float(item['price']) * item['quantity']
        text += f"🍔 {item['name']} x {item['quantity']} = {summa:.0f} so‘m\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{order_id}")]
        ]
    )

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status='confirmed' WHERE id=$1", order_id)

    await callback.message.answer(f"✅ Buyurtma #{order_id} tasdiqlandi.")
    await callback.answer("Tasdiqlandi!")


@router.callback_query(lambda c: c.data.startswith("cancel_"))
async def cancel_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE orders SET status='canceled' WHERE id=$1", order_id)

    await callback.message.answer(f"❌ Buyurtma #{order_id} bekor qilindi.")
    await callback.answer("Bekor qilindi!")

import asyncio
import logging
import os
import psycopg
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = "7745934393:AAHHqLn23Y5Vf5lDTvONpKrdtDXzXfZ16XI"  # <-- Bot tokenini kiriting
ADMIN_ID = 8133521082

DB_DSN = "postgresql://postgres:hello1212@localhost:5432/postgres"


# === LOGGING ===
logging.basicConfig(level=logging.INFO)

# === BOT VA DISP ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# === BAZA BILAN BOG'LANISH FUNKSIYASI ===
async def get_conn():
    return await psycopg.AsyncConnection.connect(DB_DSN)

# === START BUYRUG'I ===
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍔 Menyu")],
            [KeyboardButton(text="🛒 Mening savatim")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"Salom, {message.from_user.first_name}! 👋\n"
        "Fast food buyurtma berish uchun *Menyu* tugmasini bosing.",
        parse_mode="Markdown",
        reply_markup=kb
    )

    # Foydalanuvchini bazaga qo'shish
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (telegram_id, fullname) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (message.from_user.id, message.from_user.full_name)
        )
    await conn.commit()
    await conn.close()
# === ADMIN PANEL ===
class AddProductState(StatesGroup):
    name = State()
    price = State()
    image = State()

# Admin menyu
async def admin_menu(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("➕ Mahsulot qo‘shish")],
            [KeyboardButton("📋 Mahsulotlar ro‘yxati")],
            [KeyboardButton("✏️ Mahsulotni tahrirlash")],
            [KeyboardButton("❌ Mahsulotni o‘chirish")],
            [KeyboardButton("🔙 Orqaga")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔧 Admin paneliga xush kelibsiz!", reply_markup=kb)


@dp.message(Command("admin"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await admin_menu(message)


# --- Mahsulot qo'shish ---
@dp.message(F.text == "➕ Mahsulot qo‘shish")
async def add_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📝 Mahsulot nomini kiriting:")
    await state.set_state(AddProductState.name)


@dp.message(AddProductState.name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💰 Mahsulot narxini kiriting (so'mda):")
    await state.set_state(AddProductState.price)


@dp.message(AddProductState.price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Narx raqam bo‘lishi kerak!")
        return
    await state.update_data(price=int(message.text))
    await message.answer("📷 Mahsulot rasmini URL yoki rasm fayl sifatida yuboring:")
    await state.set_state(AddProductState.image)


@dp.message(AddProductState.image)
async def add_product_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.photo:
        # Agar rasm sifatida yuborilgan bo'lsa
        file = await bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}"
    else:
        image_url = message.text

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO products (name, price, image_url) VALUES (%s, %s, %s)",
            (data['name'], data['price'], image_url)
        )
    await conn.commit()
    await conn.close()

    await message.answer(f"✅ {data['name']} qo‘shildi!")
    await state.clear()
    await admin_menu(message)


# --- Mahsulotlar ro‘yxati ---
@dp.message(F.text == "📋 Mahsulotlar ro‘yxati")
async def list_products(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name, price FROM products ORDER BY id")
        products = await cur.fetchall()
    await conn.close()

    if not products:
        await message.answer("❌ Hozircha mahsulot yo‘q.")
        return

    text = "📋 <b>Mahsulotlar:</b>\n\n"
    for p in products:
        text += f"🆔 {p[0]} | {p[1]} — {p[2]} so'm\n"
    await message.answer(text, parse_mode="HTML")


# --- Mahsulot o‘chirish ---
@dp.message(F.text == "❌ Mahsulotni o‘chirish")
async def delete_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🆔 O‘chirish uchun mahsulot ID raqamini yuboring:")


@dp.message(F.text.regexp(r"^\d+$"))
async def confirm_delete_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    product_id = int(message.text)

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        deleted = cur.rowcount
    await conn.commit()
    await conn.close()

    if deleted:
        await message.answer(f"✅ ID {product_id} o‘chirildi.")
    else:
        await message.answer("❌ Bunday ID topilmadi.")


# --- Mahsulot tahrirlash ---
class EditProductState(StatesGroup):
    product_id = State()
    field = State()
    value = State()

@dp.message(F.text == "✏️ Mahsulotni tahrirlash")
async def edit_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🆔 Tahrir qilish uchun mahsulot ID raqamini yuboring:")
    await state.set_state(EditProductState.product_id)


@dp.message(EditProductState.product_id)
async def edit_product_field(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam bo‘lishi kerak!")
        return
    await state.update_data(product_id=int(message.text))
    await state.set_state(EditProductState.field)
    await message.answer("Qaysi maydonni tahrirlashni xohlaysiz?\n1. Nom\n2. Narx\n3. Rasm URL\n\n1, 2 yoki 3 kiriting:")


@dp.message(EditProductState.field)
async def edit_product_value(message: types.Message, state: FSMContext):
    if message.text not in ["1", "2", "3"]:
        await message.answer("❌ 1, 2 yoki 3 kiriting.")
        return
    await state.update_data(field=message.text)
    await state.set_state(EditProductState.value)
    await message.answer("Yangi qiymatni kiriting:")


@dp.message(EditProductState.value)
async def save_product_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id, field, new_value = data['product_id'], data['field'], message.text

    fields = {"1": "name", "2": "price", "3": "image_url"}
    field_name = fields[field]

    if field_name == "price" and not new_value.isdigit():
        await message.answer("❌ Narx raqam bo‘lishi kerak!")
        return

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            f"UPDATE products SET {field_name} = %s WHERE id = %s",
            (new_value if field_name != "price" else int(new_value), product_id)
        )
    await conn.commit()
    await conn.close()

    await message.answer("✅ Mahsulot yangilandi.")
    await state.clear()
    await admin_menu(message)
# === FOYDALANUVCHI START ===
user_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🍔 Mahsulotlar menyusi")],
        [KeyboardButton("🛒 Mening savatim")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Salom! Fast Food Delivery botiga xush kelibsiz!\n"
        "🍔 Buyurtma berish uchun pastdagi menyudan tanlang.",
        reply_markup=user_menu_kb
    )


# === MAHSULOTLAR MENYUSI ===
@dp.message(F.text == "🍔 Mahsulotlar menyusi")
async def show_products(message: types.Message):
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name, price FROM products ORDER BY id")
        products = await cur.fetchall()
    await conn.close()

    if not products:
        await message.answer("❌ Hozircha menyuda taom yo‘q.")
        return

    # Inline keyboard: har bir mahsulot tugmasi
    buttons = []
    row = []
    for idx, p in enumerate(products, start=1):
        row.append(InlineKeyboardButton(
            text=f"{p[1]} - {p[2]} so'm", callback_data=f"product_{p[0]}"
        ))
        if idx % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await message.answer(
        "🍽 <b>Menyudan mahsulot tanlang:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# === MAHSULOT DETALLARI (Rasmi, +/−, Savat) ===
@dp.callback_query(F.data.startswith("product_"))
async def product_detail(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT name, price, image_url FROM products WHERE id=%s", (product_id,)
        )
        product = await cur.fetchone()
    await conn.close()

    if not product:
        await callback.answer("❌ Mahsulot topilmadi.", show_alert=True)
        return

    quantity_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("➖", callback_data=f"decrease_{product_id}_1"),
            InlineKeyboardButton("1", callback_data=f"quantity_{product_id}_1"),
            InlineKeyboardButton("➕", callback_data=f"increase_{product_id}_1")
        ],
        [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{product_id}_1")],
        [InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_menu")]
    ])

    try:
        await callback.message.answer_photo(
            photo=product[2],
            caption=f"🍔 <b>{product[0]}</b>\n💰 Narxi: {product[1]} so'm",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )
    except:
        await callback.message.answer(
            f"🍔 <b>{product[0]}</b>\n💰 Narxi: {product[1]} so'm",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )
    await callback.answer()


# === MIQDOR O‘ZGARTIRISH (+/−) ===
@dp.callback_query(F.data.startswith(("increase_", "decrease_")))
async def change_quantity(callback: types.CallbackQuery):
    action, product_id, qty = callback.data.split("_")
    product_id, current_qty = int(product_id), int(qty)

    if action == "increase":
        current_qty += 1
    elif action == "decrease" and current_qty > 1:
        current_qty -= 1

    new_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("➖", callback_data=f"decrease_{product_id}_{current_qty}"),
            InlineKeyboardButton(str(current_qty), callback_data=f"quantity_{product_id}_{current_qty}"),
            InlineKeyboardButton("➕", callback_data=f"increase_{product_id}_{current_qty}")
        ],
        [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{product_id}_{current_qty}")],
        [InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_menu")]
    ])
    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer()


# === SAVATGA QO‘SHISH ===
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    _, product_id, quantity = callback.data.split("_")
    product_id, quantity = int(product_id), int(quantity)
    user_id = callback.from_user.id

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute('''
            INSERT INTO users (telegram_id, fullname)
            VALUES (%s, %s)
            ON CONFLICT (telegram_id) DO NOTHING
        ''', (user_id, callback.from_user.full_name))

        await cur.execute('''
            INSERT INTO cart (user_id, product_id, quantity, status)
            VALUES (%s, %s, %s, 'pending')
            ON CONFLICT (user_id, product_id, status)
            DO UPDATE SET quantity = cart.quantity + EXCLUDED.quantity
        ''', (user_id, product_id, quantity))
    await conn.commit()
    await conn.close()

    await callback.answer(f"🛒 {quantity} dona mahsulot savatga qo‘shildi!", show_alert=True)
# === MENING SAVATIM ===
@dp.message(F.text == "🛒 Mening savatim")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute('''
            SELECT p.name, p.price, c.quantity, p.image_url
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=%s AND c.status='pending'
        ''', (user_id,))
        cart_items = await cur.fetchall()
    await conn.close()

    if not cart_items:
        await message.answer("🛒 Savatingiz hozircha bo‘sh.")
        return

    total_price = 0
    for item in cart_items:
        name, price, qty, img = item
        total_price += price * qty
        try:
            await message.answer_photo(
                photo=img,
                caption=f"🍔 <b>{name}</b>\n"
                        f"💰 Narxi: {price} so'm\n"
                        f"📦 Miqdor: {qty}\n"
                        f"= <b>{price * qty} so'm</b>",
                parse_mode="HTML"
            )
        except:
            await message.answer(
                f"🍔 <b>{name}</b>\n"
                f"💰 Narxi: {price} so'm\n"
                f"📦 Miqdor: {qty}\n"
                f"= <b>{price * qty} so'm</b>",
                parse_mode="HTML"
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("✅ Xarid qilish", callback_data="checkout")],
            [InlineKeyboardButton("⬅️ Menyuga qaytish", callback_data="back_to_menu")]
        ]
    )
    await message.answer(f"💵 <b>Umumiy summa:</b> {total_price} so'm", parse_mode="HTML", reply_markup=kb)


# === XARID QILISH BOSHQAN PAYTDA ===
@dp.callback_query(F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📞 Telefon raqamingizni yuboring (+998...)")
    await state.set_state("phone")
    await callback.answer()


# === TELEFON RAQAMI QABUL QILISH ===
@dp.message(F.text.regexp(r"^\+998\d{9}$"), state="phone")
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📍 Lokatsiyangizni yuboring:", reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True
    ))
    await state.set_state("location")


# Agar noto‘g‘ri telefon kiritilsa
@dp.message(state="phone")
async def wrong_phone(message: types.Message):
    await message.answer("❌ Telefon raqam formati xato. Qaytadan kiriting: (+998XXXXXXXXX)")


# === LOKATSIYA QABUL QILISH ===
@dp.message(F.location, state="location")
async def get_location(message: types.Message, state: FSMContext):
    loc = message.location
    await state.update_data(location=f"{loc.latitude},{loc.longitude}")
    await message.answer(
        "💳 To‘lov turini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💵 Naqd", callback_data="pay_cash")],
            [InlineKeyboardButton("💳 Karta", callback_data="pay_card")]
        ])
    )
    await state.set_state("payment")


@dp.message(state="location")
async def wrong_location(message: types.Message):
    await message.answer("❌ Lokatsiyani yuboring.")


# === TO‘LOV TURINI TANLASH ===
@dp.callback_query(F.data.in_(["pay_cash", "pay_card"]))
async def payment_type(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    phone = data.get("phone")
    location = data.get("location")

    conn = await get_conn()
    async with conn.cursor() as cur:
        # Savatdagi mahsulotlarni orderga ko‘chirish
        await cur.execute('''
            SELECT p.name, p.price, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=%s AND c.status='pending'
        ''', (user_id,))
        cart_items = await cur.fetchall()

        total_price = sum(p[1] * p[2] for p in cart_items)

        await cur.execute('''
            INSERT INTO orders (user_id, total_price, payment_type, phone, location, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
            RETURNING id
        ''', (user_id, total_price, "naqd" if callback.data == "pay_cash" else "karta", phone, location))
        order_id = (await cur.fetchone())[0]

        await cur.execute('''
            UPDATE cart SET status='ordered'
            WHERE user_id=%s AND status='pending'
        ''', (user_id,))
    await conn.commit()
    await conn.close()

    if callback.data == "pay_cash":
        await callback.message.answer("✅ Buyurtmangiz qabul qilindi. Admin siz bilan bog‘lanadi.", reply_markup=user_menu_kb)
        await send_order_to_admin(order_id, cart_items, total_price, phone, location, "Naqd")
        await state.clear()
    else:
        await callback.message.answer("💳 To‘lov uchun karta raqami: 9860 1234 5678 9000\n\nChek rasmini yuboring.")
        await state.set_state("check_photo")
        await state.update_data(order_id=order_id)
        await send_order_to_admin(order_id, cart_items, total_price, phone, location, "Karta (tasdiqlash kutilmoqda)")
# === CHEK YUBORISH (KARTA TO'LOVI) ===
@dp.message(F.photo, state="check_photo")
async def receive_check_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    photo_id = message.photo[-1].file_id

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE orders SET check_photo=%s, status='waiting_confirm' WHERE id=%s",
            (photo_id, order_id)
        )
    await conn.commit()
    await conn.close()

    # Adminga chek yuboriladi
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}")],
        [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")]
    ])
    await bot.send_photo(
        ADMIN_ID,
        photo=photo_id,
        caption=f"📥 <b>Yangi karta to‘lov buyurtmasi</b>\n\n"
                f"🆔 Buyurtma ID: {order_id}\n"
                f"👤 Foydalanuvchi: {message.from_user.full_name} ({message.from_user.id})\n"
                f"📞 Telefon: {data.get('phone')}\n"
                f"📍 Lokatsiya: {data.get('location')}",
        parse_mode="HTML",
        reply_markup=kb
    )

    await message.answer("✅ Chek yuborildi. Admin tasdiqlashini kuting.", reply_markup=user_menu_kb)
    await state.clear()


# === ADMIN TASDIQLASH ===
@dp.callback_query(F.data.startswith("confirm_"))
async def admin_confirm_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz.")
        return

    order_id = int(callback.data.split("_")[1])

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("UPDATE orders SET status='confirmed' WHERE id=%s", (order_id,))
        await cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        user_id = (await cur.fetchone())[0]
    await conn.commit()
    await conn.close()

    await bot.send_message(user_id, f"✅ Buyurtmangiz tasdiqlandi!\nBuyurtma ID: {order_id}")
    await callback.message.edit_caption(
        callback.message.caption + "\n\n✅ Tasdiqlandi."
    )
    await callback.answer("Tasdiqlandi!")


# === ADMIN RAD ETISH ===
@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz.")
        return

    order_id = int(callback.data.split("_")[1])

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("UPDATE orders SET status='rejected' WHERE id=%s", (order_id,))
        await cur.execute("SELECT user_id FROM orders WHERE id=%s", (order_id,))
        user_id = (await cur.fetchone())[0]
    await conn.commit()
    await conn.close()

    await bot.send_message(user_id, f"❌ Chekingiz rad etildi. Buyurtma ID: {order_id}")
    await callback.message.edit_caption(
        callback.message.caption + "\n\n❌ Rad etildi."
    )
    await callback.answer("Rad etildi!")
# === YANGI XARID BOSHLASH ===
@dp.message(F.text == "🔄 Yangi xarid boshlash")
async def new_purchase(message: types.Message):
    await message.answer("🛒 Yangi xaridni boshlash uchun <b>Mahsulotlar</b> menyusini tanlang.",
                         parse_mode="HTML",
                         reply_markup=user_menu_kb)


# =======================
# === ADMIN PANELI ===
# =======================

# --- Admin menyu ---
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📦 Mahsulotlar ro‘yxati")],
        [KeyboardButton("➕ Mahsulot qo‘shish")],
        [KeyboardButton("❌ Mahsulotni o‘chirish")],
        [KeyboardButton("✏️ Mahsulotni tahrirlash")],
        [KeyboardButton("🔙 Foydalanuvchi menyusiga qaytish")]
    ],
    resize_keyboard=True
)


@dp.message(Command("admin"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("🔧 <b>Admin paneliga xush kelibsiz!</b>", parse_mode="HTML", reply_markup=admin_kb)


# --- Mahsulotlar ro‘yxati ---
@dp.message(F.text == "📦 Mahsulotlar ro‘yxati")
async def list_products(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name, price FROM products ORDER BY id")
        products = await cur.fetchall()
    await conn.close()

    if not products:
        await message.answer("❌ Mahsulotlar mavjud emas.")
        return

    text = "📦 <b>Mahsulotlar ro‘yxati:</b>\n\n"
    for p in products:
        text += f"🆔 {p[0]} — {p[1]} ({p[2]} so‘m)\n"
    await message.answer(text, parse_mode="HTML")


# --- Mahsulot qo‘shish ---
class AddProduct(StatesGroup):
    name = State()
    price = State()
    image = State()

@dp.message(F.text == "➕ Mahsulot qo‘shish")
async def add_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProduct.name)
    await message.answer("🍔 Mahsulot nomini kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(AddProduct.name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Mahsulot narxini kiriting (so‘mda):")

@dp.message(AddProduct.price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Narx raqam bo‘lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddProduct.image)
    await message.answer("🖼 Mahsulot rasmini yuboring (URL yoki rasm):")

@dp.message(AddProduct.image)
async def add_product_image(message: types.Message, state: FSMContext):
    data = await state.get_data()

    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    else:
        image_url = message.text

    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO products (name, price, image_url) VALUES (%s, %s, %s)",
            (data['name'], data['price'], image_url)
        )
    await conn.commit()
    await conn.close()

    await message.answer(f"✅ <b>{data['name']}</b> mahsuloti qo‘shildi!", parse_mode="HTML", reply_markup=admin_kb)
    await state.clear()


# --- Mahsulot o‘chirish ---
@dp.message(F.text == "❌ Mahsulotni o‘chirish")
async def delete_product_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🆔 O‘chirish uchun mahsulot ID raqamini kiriting:")
    await dp.storage.set_state(message.from_user.id, "delete_product")


@dp.message(F.text.regexp(r"^\d+$"), state="delete_product")
async def delete_product(message: types.Message, state: FSMContext):
    product_id = int(message.text)
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        deleted = cur.rowcount
    await conn.commit()
    await conn.close()

    if deleted:
        await message.answer(f"✅ Mahsulot (ID {product_id}) o‘chirildi.", reply_markup=admin_kb)
    else:
        await message.answer("❌ Bunday ID bilan mahsulot topilmadi.", reply_markup=admin_kb)
    await state.clear()


# --- Mahsulotni tahrirlash ---
class EditProduct(StatesGroup):
    id = State()
    field = State()
    value = State()

@dp.message(F.text == "✏️ Mahsulotni tahrirlash")
async def edit_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(EditProduct.id)
    await message.answer("🆔 Tahrirlash uchun mahsulot ID raqamini kiriting:")

@dp.message(EditProduct.id)
async def edit_product_choose_field(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam bo‘lishi kerak!")
        return
    await state.update_data(id=int(message.text))
    await state.set_state(EditProduct.field)
    await message.answer("Qaysi maydonni tahrirlashni xohlaysiz?\n1️⃣ Nom\n2️⃣ Narx\n3️⃣ Rasm URL")

@dp.message(EditProduct.field)
async def edit_product_value(message: types.Message, state: FSMContext):
    if message.text not in ["1", "2", "3"]:
        await message.answer("❌ 1, 2 yoki 3 ni tanlang.")
        return
    await state.update_data(field=message.text)
    await state.set_state(EditProduct.value)
    await message.answer("Yangi qiymatni kiriting:")

@dp.message(EditProduct.value)
async def edit_product_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data['id']
    field = data['field']
    new_value = message.text

    field_map = {"1": "name", "2": "price", "3": "image_url"}
    field_name = field_map[field]

    conn = await get_conn()
    async with conn.cursor() as cur:
        if field_name == "price" and not new_value.isdigit():
            await message.answer("❌ Narx raqam bo‘lishi kerak!")
            return
        await cur.execute(f"UPDATE products SET {field_name}=%s WHERE id=%s", (new_value, product_id))
    await conn.commit()
    await conn.close()

    await message.answer("✅ Mahsulot yangilandi.", reply_markup=admin_kb)
    await state.clear()

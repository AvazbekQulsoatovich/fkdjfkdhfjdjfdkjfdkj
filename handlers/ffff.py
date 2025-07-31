import asyncio
import logging
import psycopg2
import psycopg2.extras
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# -------------------
# CONFIG
# -------------------
TOKEN = "7745934393:AAHHqLn23Y5Vf5lDTvONpKrdtDXzXfZ16XI"
ADMIN_ID = 8133521082
DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'hello1212',
    'host': 'localhost'
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# -------------------
# DB CONNECTION
# -------------------
def db_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)

# -------------------
# KEYBOARDS
# -------------------
user_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍔 Mahsulotlar")],
        [KeyboardButton(text="🛒 Mening savatim")],
        [KeyboardButton(text="🔄 Yangi xarid boshlash")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Mahsulotlar ro‘yxati")],
        [KeyboardButton(text="➕ Mahsulot qo‘shish")],
        [KeyboardButton(text="❌ Mahsulotni o‘chirish")],
        [KeyboardButton(text="✏️ Mahsulotni tahrirlash")],
        [KeyboardButton(text="🔙 Foydalanuvchi menyusiga qaytish")]
    ],
    resize_keyboard=True
)

# -------------------
# START
# -------------------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 <b>Fast Food Delivery Botiga xush kelibsiz!</b>\n\n"
        "🍟 Buyurtma berish uchun <b>Mahsulotlar</b> bo‘limiga o‘ting.",
        parse_mode="HTML",
        reply_markup=user_menu_kb
    )

# -------------------
# MAHSULOTLAR RO‘YXATI
# -------------------
@dp.message(F.text == "🍔 Mahsulotlar")
async def show_products(message: types.Message):
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, price FROM products ORDER BY id;")
        products = cur.fetchall()
    conn.close()

    if not products:
        await message.answer("❌ Mahsulotlar mavjud emas.")
        return

    buttons = []
    row = []
    for idx, p in enumerate(products, start=1):
        row.append(InlineKeyboardButton(text=f"{p['name']} - {p['price']} so‘m",
                                        callback_data=f"product_{p['id']}"))
        if idx % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🍽 <b>Mahsulotlar ro‘yxati:</b>", parse_mode="HTML", reply_markup=kb)

# -------------------
# MAHSULOT DETALLARI
# -------------------
@dp.callback_query(F.data.startswith("product_"))
async def product_details(callback: types.CallbackQuery):
    await callback.answer()
    product_id = int(callback.data.split("_")[1])

    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM products WHERE id=%s;", (product_id,))
        product = cur.fetchone()
    conn.close()

    if not product:
        await callback.message.answer("❌ Mahsulot topilmadi!")
        return

    quantity_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text="1", callback_data=f"quantity_{product_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [InlineKeyboardButton(text="🛒 Savatga qo‘shish", callback_data=f"add_{product_id}_1")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_menu")]
    ])

    try:
        await callback.message.answer_photo(
            product['image_url'],
            caption=f"🍔 <b>{product['name']}</b>\n💰 {product['price']} so‘m",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )
    except:
        await callback.message.answer(
            f"🍔 <b>{product['name']}</b>\n💰 {product['price']} so‘m",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )

# -------------------
# SAVATGA QO‘SHISH
# -------------------
@dp.callback_query(F.data.startswith(("increase_", "decrease_")))
async def change_quantity(callback: types.CallbackQuery):
    action, product_id = callback.data.split("_")
    product_id = int(product_id)

    buttons = callback.message.reply_markup.inline_keyboard
    current_quantity = int(buttons[0][1].text)

    if action == "increase":
        current_quantity += 1
    elif action == "decrease" and current_quantity > 1:
        current_quantity -= 1

    quantity_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(str(current_quantity), callback_data=f"quantity_{product_id}"),
            InlineKeyboardButton("➕", callback_data=f"increase_{product_id}")
        ],
        [InlineKeyboardButton("🛒 Savatga qo‘shish", callback_data=f"add_{product_id}_{current_quantity}")],
        [InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_menu")]
    ])

    await callback.message.edit_reply_markup(reply_markup=quantity_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    _, product_id, quantity = callback.data.split("_")
    product_id, quantity = int(product_id), int(quantity)
    user_id = callback.from_user.id

    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (telegram_id, fullname) VALUES (%s,%s) ON CONFLICT (telegram_id) DO NOTHING;",
                    (user_id, callback.from_user.full_name))
        cur.execute("""
            INSERT INTO cart (user_id, product_id, quantity, status)
            VALUES (%s,%s,%s,'pending')
            ON CONFLICT (user_id, product_id, status)
            DO UPDATE SET quantity = cart.quantity + %s;
        """, (user_id, product_id, quantity, quantity))
    conn.commit()
    conn.close()

    await callback.answer(f"🛒 {quantity} dona mahsulot savatga qo‘shildi!", show_alert=False)

# -------------------
# SAVATNI KO‘RISH
# -------------------
@dp.message(F.text == "🛒 Mening savatim")
async def view_cart(message: types.Message):
    user_id = message.from_user.id
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.product_id, c.quantity, p.name, p.price, p.image_url
            FROM cart c
            JOIN products p ON p.id=c.product_id
            WHERE c.user_id=%s AND c.status='pending';
        """, (user_id,))
        items = cur.fetchall()
    conn.close()

    if not items:
        await message.answer("❌ Savatingiz bo‘sh.")
        return

    total = sum(item['price'] * item['quantity'] for item in items)
    text = "🛒 <b>Savatingiz:</b>\n\n"
    for item in items:
        text += f"🍔 {item['name']} x {item['quantity']} = {item['price']*item['quantity']} so‘m\n"
    text += f"\n💰 <b>Umumiy:</b> {total} so‘m"

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("✅ Xarid qilish")],
            [KeyboardButton("🔄 Yangi xarid boshlash")]
        ],
        resize_keyboard=True
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# -------------------
# XARID QILISH
# -------------------
class OrderState(StatesGroup):
    phone = State()
    location = State()
    payment = State()
    payment_photo = State()

@dp.message(F.text == "✅ Xarid qilish")
async def start_order(message: types.Message, state: FSMContext):
    await state.set_state(OrderState.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=kb)

@dp.message(OrderState.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await state.set_state(OrderState.location)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True
    )
    await message.answer("📍 Lokatsiyangizni yuboring:", reply_markup=kb)

@dp.message(OrderState.location, F.location)
async def get_location(message: types.Message, state: FSMContext):
    location = f"{message.location.latitude},{message.location.longitude}"
    await state.update_data(location=location)
    await state.set_state(OrderState.payment)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("💵 Naqd"), KeyboardButton("💳 Karta")]],
        resize_keyboard=True
    )
    await message.answer("💳 To‘lov turini tanlang:", reply_markup=kb)

@dp.message(OrderState.payment, F.text)
async def choose_payment(message: types.Message, state: FSMContext):
    if message.text == "💵 Naqd":
        await finalize_order(message, state, payment_type="naqd")
    elif message.text == "💳 Karta":
        await state.update_data(payment="karta")
        await state.set_state(OrderState.payment_photo)
        await message.answer("💳 To‘lov uchun karta raqam: 8600 **** **** ****\n\nTo‘lov chekini yuboring.")
    else:
        await message.answer("❌ Faqat 'Naqd' yoki 'Karta' ni tanlang.")

@dp.message(OrderState.payment_photo, F.photo)
async def payment_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await finalize_order(message, state, payment_type="karta", photo_id=photo_id)

# -------------------
# BUYURTMA YAKUNI
# -------------------
async def finalize_order(message: types.Message, state: FSMContext, payment_type: str, photo_id=None):
    user_id = message.from_user.id
    data = await state.get_data()

    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.product_id, c.quantity, p.name, p.price
            FROM cart c
            JOIN products p ON p.id=c.product_id
            WHERE c.user_id=%s AND c.status='pending';
        """, (user_id,))
        items = cur.fetchall()

        total = sum(item['price'] * item['quantity'] for item in items)
        cur.execute("""
            INSERT INTO orders (user_id, phone, location, total_price, payment_type)
            VALUES (%s,%s,%s,%s,%s) RETURNING id;
        """, (user_id, data['phone'], data['location'], total, payment_type))
        order_id = cur.fetchone()['id']

        for item in items:
            cur.execute("""
                INSERT INTO orders_items (order_id, product_id, quantity, price)
                VALUES (%s,%s,%s,%s);
            """, (order_id, item['product_id'], item['quantity'], item['price']))

        cur.execute("DELETE FROM cart WHERE user_id=%s AND status='pending';", (user_id,))
    conn.commit()
    conn.close()

    await state.clear()

    text = f"📦 <b>Yangi buyurtma #{order_id}</b>\n" \
           f"👤 {message.from_user.full_name}\n" \
           f"📞 {data['phone']}\n" \
           f"📍 {data['location']}\n" \
           f"💰 {total} so‘m\n" \
           f"💳 To‘lov turi: {payment_type}\n\n"

    for item in items:
        text += f"🍔 {item['name']} x {item['quantity']} = {item['price'] * item['quantity']} so‘m\n"

    if payment_type == "karta" and photo_id:
        await bot.send_photo(ADMIN_ID, photo=photo_id, caption=text, parse_mode="HTML")
    else:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")

    await message.answer("✅ Xaridingiz uchun rahmat! Admin tez orada bog‘lanadi.", reply_markup=user_menu_kb)

# -------------------
# ADMIN PANEL (CRUD)
# -------------------
class AddProduct(StatesGroup):
    name = State()
    price = State()
    image = State()

class DeleteProduct(StatesGroup):
    product_id = State()

class EditProduct(StatesGroup):
    product_id = State()
    field = State()
    new_value = State()

@dp.message(Command("admin"))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("🔧 <b>Admin paneliga xush kelibsiz!</b>", parse_mode="HTML", reply_markup=admin_kb)

# --- ADMIN CRUD: LIST
@dp.message(F.text == "📦 Mahsulotlar ro‘yxati")
async def admin_list_products(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, price FROM products ORDER BY id;")
        products = cur.fetchall()
    conn.close()

    if not products:
        await message.answer("❌ Mahsulotlar yo‘q.")
        return

    text = "📦 <b>Mahsulotlar:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} — {p['name']} ({p['price']} so‘m)\n"
    await message.answer(text, parse_mode="HTML")

# --- ADMIN CRUD: ADD
@dp.message(F.text == "➕ Mahsulot qo‘shish")
async def admin_add_product(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProduct.name)
    await message.answer("🍔 Yangi mahsulot nomini kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(AddProduct.name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Mahsulot narxini kiriting:")

@dp.message(AddProduct.price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Narx raqam bo‘lishi kerak.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddProduct.image)
    await message.answer("🖼 Mahsulot rasmini yuboring (URL yoki rasm):")

@dp.message(AddProduct.image)
async def add_product_image(message: types.Message, state: FSMContext):
    data = await state.get_data()
    image_url = message.text
    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        image_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO products (name, price, image_url) VALUES (%s,%s,%s);",
                    (data['name'], data['price'], image_url))
    conn.commit()
    conn.close()

    await message.answer(f"✅ {data['name']} mahsuloti qo‘shildi.", reply_markup=admin_kb)
    await state.clear()

# --- ADMIN CRUD: DELETE
@dp.message(F.text == "❌ Mahsulotni o‘chirish")
async def admin_delete_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, price FROM products ORDER BY id;")
        products = cur.fetchall()
    conn.close()

    if not products:
        await message.answer("❌ Mahsulotlar yo‘q.")
        return

    text = "❌ <b>O‘chirish uchun mahsulot ID sini kiriting:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} — {p['name']} ({p['price']} so‘m)\n"
    await state.set_state(DeleteProduct.product_id)
    await message.answer(text, parse_mode="HTML")

@dp.message(DeleteProduct.product_id)
async def admin_delete_product_confirm(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam bo‘lishi kerak!")
        return
    product_id = int(message.text)

    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM products WHERE id=%s RETURNING id;", (product_id,))
        deleted = cur.fetchone()
    conn.commit()
    conn.close()

    if deleted:
        await message.answer(f"✅ Mahsulot #{product_id} o‘chirildi.", reply_markup=admin_kb)
    else:
        await message.answer("❌ Bunday ID mavjud emas.", reply_markup=admin_kb)

    await state.clear()

# --- ADMIN CRUD: EDIT
@dp.message(F.text == "✏️ Mahsulotni tahrirlash")
async def admin_edit_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, price FROM products ORDER BY id;")
        products = cur.fetchall()
    conn.close()

    if not products:
        await message.answer("❌ Mahsulotlar yo‘q.")
        return

    text = "✏️ <b>Tahrirlash uchun mahsulot ID sini kiriting:</b>\n\n"
    for p in products:
        text += f"🆔 {p['id']} — {p['name']} ({p['price']} so‘m)\n"
    await state.set_state(EditProduct.product_id)
    await message.answer(text, parse_mode="HTML")

@dp.message(EditProduct.product_id)
async def admin_edit_product_field(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID raqam bo‘lishi kerak!")
        return
    await state.update_data(product_id=int(message.text))
    await state.set_state(EditProduct.field)
    await message.answer("Qaysi maydonni tahrirlashni xohlaysiz? (name/price/image_url)")

@dp.message(EditProduct.field)
async def admin_edit_product_new_value(message: types.Message, state: FSMContext):
    field = message.text.lower()
    if field not in ["name", "price", "image_url"]:
        await message.answer("❌ Faqat name, price yoki image_url ni tanlang!")
        return
    await state.update_data(field=field)
    await state.set_state(EditProduct.new_value)
    await message.answer(f"Yangi qiymatni kiriting ({field}):")

@dp.message(EditProduct.new_value)
async def admin_edit_product_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_value = message.text

    conn = db_conn()
    with conn.cursor() as cur:
        if data['field'] == "price":
            if not new_value.isdigit():
                await message.answer("❌ Narx raqam bo‘lishi kerak!")
                return
            cur.execute(f"UPDATE products SET {data['field']}=%s WHERE id=%s;",
                        (int(new_value), data['product_id']))
        else:
            cur.execute(f"UPDATE products SET {data['field']}=%s WHERE id=%s;",
                        (new_value, data['product_id']))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Mahsulot #{data['product_id']} yangilandi.", reply_markup=admin_kb)
    await state.clear()

# -------------------
# BOTNI ISHGA TUSHURISH
# -------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from db import create_pool

router = Router()

# --- FSM: Telefon va Lokatsiya ---
class Checkout(StatesGroup):
    phone = State()
    location = State()

# --- Mahsulotlar menyusini ko‘rsatish ---
@router.message(F.text == "🍔 Mahsulotlar menyusi")
async def show_menu(message: types.Message):
    pool = await create_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT id, name FROM products")

    if not products:
        await message.answer("Hozircha menyuda taomlar yo‘q. ❌")
        return

    buttons = []
    row = []
    for idx, p in enumerate(products, start=1):
        row.append(InlineKeyboardButton(text=p["name"], callback_data=f"product_{p['id']}"))
        if idx % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🍔 <b>Menyudan taom tanlang:</b>", parse_mode="HTML", reply_markup=kb)

# --- Mahsulot detallarini ko‘rsatish ---
@router.callback_query(F.data.startswith("product_"))
async def show_product_details(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])

    pool = await create_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow(
            "SELECT id, name, price, image_url FROM products WHERE id=$1",
            product_id
        )

    if not product:
        await callback.answer("Mahsulot topilmadi. ❌", show_alert=True)
        return

    quantity_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text="1", callback_data=f"quantity_{product_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"add_{product_id}_1")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_menu")]
    ])

    # Rasm bilan jo‘natish
    try:
        await callback.message.answer_photo(
            photo=product["image_url"],
            caption=f"🍽 <b>{product['name']}</b>\n💰 Narxi: {product['price']} so‘m",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )
    except:
        # Agar rasm URL noto‘g‘ri bo‘lsa
        await callback.message.answer(
            text=f"🍽 <b>{product['name']}</b>\n💰 Narxi: {product['price']} so‘m",
            parse_mode="HTML",
            reply_markup=quantity_kb
        )

# --- Miqdor o‘zgartirish (+/-) ---
@router.callback_query(F.data.startswith(("increase_", "decrease_")))
async def change_quantity(callback: types.CallbackQuery):
    action, product_id = callback.data.split("_")
    product_id = int(product_id)

    buttons = callback.message.reply_markup.inline_keyboard
    current_quantity = 1
    for btn in buttons[0]:
        if "quantity_" in btn.callback_data:
            current_quantity = int(btn.text)

    if action == "increase":
        current_quantity += 1
    elif action == "decrease" and current_quantity > 1:
        current_quantity -= 1

    quantity_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text=str(current_quantity), callback_data=f"quantity_{product_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}")
        ],
        [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"add_{product_id}_{current_quantity}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_menu")]
    ])

    await callback.message.edit_reply_markup(reply_markup=quantity_kb)
    await callback.answer()

# --- Savatga qo‘shish ---
@router.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    _, product_id, quantity = callback.data.split("_")
    product_id = int(product_id)
    quantity = int(quantity)
    user_id = callback.from_user.id

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (telegram_id, fullname)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO NOTHING
        ''', user_id, callback.from_user.full_name)

        await conn.execute('''
            INSERT INTO cart (user_id, product_id, quantity, status)
            VALUES ($1, $2, $3, 'pending')
            ON CONFLICT (user_id, product_id, status)
            DO UPDATE SET quantity = cart.quantity + $3
        ''', user_id, product_id, quantity)

    await callback.answer(f"🛒 {quantity} dona mahsulot savatga qo‘shildi!", show_alert=False)

    # Telefon raqamini so‘raymiz
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )
    await callback.message.answer("📞 Buyurtma uchun telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(Checkout.phone)

# --- Telefon qabul qilish ---
@router.message(Checkout.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True
    )
    await message.answer("📍 Endi yetkazib berish manzilingizni yuboring:", reply_markup=kb)
    await state.set_state(Checkout.location)

# --- Lokatsiya qabul qilish ---
@router.message(Checkout.location, F.location)
async def get_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data.get("phone")
    location = f"{message.location.latitude},{message.location.longitude}"

    pool = await create_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET phone=$1, location=$2 WHERE telegram_id=$3",
            phone, location, message.from_user.id
        )

    await message.answer(
        f"✅ Buyurtmangiz qabul qilindi!\n📞 Tel: {phone}\n📍 Manzil: {location}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

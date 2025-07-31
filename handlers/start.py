from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from config import ADMIN_ID  # Admin ID ni import qilamiz

router = Router()

@router.message(Command("start"))
async def start_handler(message: types.Message):
    # Asosiy menyu tugmalari
    buttons = [
        [KeyboardButton(text="🍔 Mahsulotlar menyusi")],
        [KeyboardButton(text="🛒 Savat")]
    ]

    # Agar foydalanuvchi admin bo‘lsa, buyurtmalar tugmasini qo‘shamiz
    if message.from_user.id == ADMIN_ID:
        buttons.append([KeyboardButton(text="📦 Buyurtmalar (Admin)")])

    # Klaviaturani yaratamiz
    kb = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    # Javob qaytaramiz
    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "🍟 <b>FastFood botiga xush kelibsiz.</b>\n"
        "Quyidagi tugmalar orqali menyuni ko‘ring yoki savatingizni boshqaring.",
        parse_mode="HTML",
        reply_markup=kb
    )

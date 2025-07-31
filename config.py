import os
from dotenv import load_dotenv

# .env faylni yuklaymiz
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=ENV_PATH)

# .env dagi kalitlarni o'qiymiz
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 8133521082  # O'zingizning Telegram ID ni yozing


# Debug uchun (tekshiruv)
print("BOT_TOKEN:", BOT_TOKEN)
print("DATABASE_URL:", DATABASE_URL)

# Agar tokenlar bo'sh bo'lsa, xato chiqaramiz
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylda topilmadi!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL .env faylda topilmadi!")

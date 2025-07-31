import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from db import create_pool, init_db
from handlers import start, menu, cart, order, orders, admin

async def main():
    # Bot va Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(cart.router)
    dp.include_router(order.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)

    # Ma'lumotlar bazasini ishga tayyorlash
    pool = await create_pool()
    await init_db(pool)

    print("✅ Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

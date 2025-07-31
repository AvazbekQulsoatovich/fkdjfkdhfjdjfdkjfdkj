import asyncpg
from config import DATABASE_URL

# Global pool (faqat bir marta yaratiladi)
_pool = None

async def create_pool():
    global _pool
    if _pool is None:
        # max_size = 10 (bir vaqtning o'zida 10 ta ulanishga ruxsat)
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

async def init_db(pool):
    async with pool.acquire() as conn:
        # Users jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                fullname TEXT,
                phone TEXT,
                location TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Products jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT,
                price NUMERIC(10,2),
                image_url TEXT
            )
        ''')

        # Cart jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                product_id INT,
                quantity INT,
                status TEXT DEFAULT 'pending'
            )
        ''')

        # Orders jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                total_price NUMERIC(10,2),
                payment_type TEXT,
                check_image TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                status TEXT DEFAULT 'pending'
            )
        ''')

import os

import asyncpg

from core.config import dp


async def get_db_pool():
    db_pool = await asyncpg.create_pool(host=os.environ['DB_HOST'],
                                        database=os.environ['DB_NAME'],
                                        user=os.environ['DB_USER'],
                                        password=os.environ['DB_PASSWORD'])
    return db_pool


async def check_or_add_user(user_id, tracker_id=None, welcome_id=None):
    async with dp.db_pool.acquire() as connection:
        data = (await connection.fetch('SELECT * FROM "User" WHERE id=$1', user_id))
        if not data:
            await connection.execute('INSERT INTO "User"(id, tracker, welcome) VALUES ($1, $2, $3)',
                                     user_id, tracker_id, welcome_id)
        else:
            if data[0][5]:
                await connection.execute('UPDATE "User" SET num_notification = 0 WHERE id=$1', user_id)


async def get_users(user_id=None):
    async with dp.db_pool.acquire() as connection:
        if user_id is None:
            data = await connection.fetch('SELECT * FROM "User"')
            return [{'id': l[0], 'createdAt': l[1], 'place': l[2], 'updated': l[3], 'game': l[4], 'num_notif': l[5],
                     'deleted': l[6], 'tracker': l[7], 'welcome': l[8]} for l in data]
        else:
            l = (await connection.fetch('SELECT * FROM "User" WHERE id = $1', user_id))[0]
            return {'id': l[0], 'createdAt': l[1], 'place': l[2], 'updated': l[3], 'game': l[4], 'num_notif': l[5],
                    'deleted': l[6], 'tracker': l[7], 'welcome': l[8]}


async def update_user(user_id, data):
    async with dp.db_pool.acquire() as connection:
        for key in data:
            await connection.execute(f'UPDATE "User" SET {key} = $1 WHERE id = $2', data[key], user_id)
        await connection.execute(f'UPDATE "User" SET updated = DEFAULT WHERE id = $1', user_id)

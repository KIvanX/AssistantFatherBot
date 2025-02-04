import os
import asyncpg
from .config import dp


async def get_db_pool():
    db_pool = await asyncpg.create_pool(host=os.environ['DB_HOST'],
                                        database=os.environ['DB_NAME'],
                                        user=os.environ['DB_USER'],
                                        password=os.environ['DB_PASSWORD'])
    return db_pool


async def get_users(user_id=None):
    async with dp.db_pool.acquire() as connection:
        if user_id is None:
            return list(map(dict, list(await connection.fetch('SELECT * FROM users'))))
        else:
            user = await connection.fetch('SELECT * FROM users WHERE id = $1', user_id)
            return dict(user[0]) if user else {}


async def update_user(user_id: int, data: dict):
    async with dp.db_pool.acquire() as connection:
        for key in data:
            await connection.execute(f'UPDATE users SET {key} = $1 WHERE id = $2', data[key], user_id)
        await connection.execute(f'UPDATE users SET updated_at = DEFAULT WHERE id = $1', user_id)


async def get_assistants(user_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        return await connection.fetch('SELECT * FROM assistants WHERE user_id = $1', user_id)


async def get_assistant(assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        assistant = dict(await connection.fetchrow('SELECT * FROM assistants WHERE id = $1', assistant_id))
        return assistant


async def update_assistant(assistant_id: int, data: dict):
    async with dp.db_pool.acquire() as connection:
        for key in data:
            await connection.execute(f'UPDATE assistants SET {key} = $1 WHERE id = $2', data[key], assistant_id)


async def get_documents(assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        data = await connection.fetch('SELECT * FROM documents WHERE assistant_id = $1', assistant_id)
        return [dict(doc) for doc in data]


async def get_document(document_id: int) -> dict:
    async with dp.db_pool.acquire() as connection:
        return dict(await connection.fetchrow('SELECT * FROM documents WHERE id = $1', document_id))


async def add_assistant_user(user_id: int, name: str, assistant_id: int):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('INSERT INTO assistant_users(user_id, name, assistant_id) VALUES ($1, $2, $3)',
                                 user_id, name, assistant_id)


async def get_assistant_users(assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        data = await connection.fetch('SELECT * FROM assistant_users WHERE assistant_id = $1', assistant_id)
        return [dict(user) for user in data]


async def update_assistant_user(user_id: int, data: dict):
    async with dp.db_pool.acquire() as connection:
        for key in data:
            await connection.execute(f'UPDATE assistant_users SET {key} = $1 WHERE user_id = $2', data[key], user_id)


async def add_message(user_id: int, assistant_id: int, author: str, message: str, price=0, model=''):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('INSERT INTO messages(user_id, assistant_id, author, message, price, model) '
                                 'VALUES ($1, $2, $3, $4, $5, $6)',
                                 user_id, assistant_id, author, message, price, model)


async def get_messages(user_id: int, assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        data = await connection.fetch('SELECT * FROM messages WHERE user_id = $1 AND assistant_id = $2 '
                                      'ORDER BY created_at', user_id, assistant_id)
        return [dict(message) for message in data]


async def get_statistics(assistant_id: int) -> dict:
    statistic = {}
    async with dp.db_pool.acquire() as connection:
        users_qsl = "SELECT * FROM assistant_users WHERE assistant_id = $1"
        res = await connection.fetch(users_qsl, assistant_id)
        statistic['users'] = len(res)
        res = await connection.fetch(users_qsl + " AND now() - created_at < '1 hour'::interval;", assistant_id)
        statistic['new_per_hour'] = len(res)
        res = await connection.fetch(users_qsl + " AND now() - created_at < '1 day'::interval;", assistant_id)
        statistic['new_per_day'] = len(res)
        res = await connection.fetch(users_qsl + " AND now() - created_at < '1 month'::interval;", assistant_id)
        statistic['new_per_month'] = len(res)

        mes_qsl = "SELECT * FROM messages WHERE assistant_id = $1"
        res = await connection.fetch(users_qsl, assistant_id)
        statistic['messages'] = len(res)
        res = await connection.fetch(mes_qsl + " AND now() - created_at < '1 hour'::interval;", assistant_id)
        statistic['new_mes_hour'] = len(res)
        res = await connection.fetch(mes_qsl + " AND now() - created_at < '1 day'::interval;", assistant_id)
        statistic['new_mes_day'] = len(res)
        res = await connection.fetch(mes_qsl + " AND now() - created_at < '1 month'::interval;", assistant_id)
        statistic['new_mes_month'] = len(res)

        res = await connection.fetch(users_qsl + " AND is_deleted = false;", assistant_id)
        statistic['alive_users'] = len(res)
        return statistic


async def get_translations() -> dict:
    async with dp.db_pool.acquire() as connection:
        tr = {}
        for line in await connection.fetch('SELECT * FROM translate'):
            tr[line[0]] = {'ru': line[0], 'en': line[1], 'it': line[2], 'fr': line[3],
                           'de': line[4], 'ja': line[5], 'zh': line[6], 'ar': line[7]}
        return tr


async def add_translation(translate: dict):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('INSERT INTO translate VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
                                 translate['ru'], translate['en'], translate['it'], translate['fr'],
                                 translate['de'], translate['ja'], translate['zh'], translate['ar'])

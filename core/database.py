import os
import asyncpg
from core.config import dp


async def get_db_pool():
    db_pool = await asyncpg.create_pool(host=os.environ['DB_HOST'],
                                        database=os.environ['DB_NAME'],
                                        user=os.environ['DB_USER'],
                                        password=os.environ['DB_PASSWORD'])
    return db_pool


async def add_user(user_id: int):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('INSERT INTO users(id, balance) VALUES ($1, $2)', user_id, 100)


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
        return await connection.fetch('SELECT * FROM assistants WHERE user_id = $1 ORDER BY id', user_id)


async def get_assistant(assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        return dict(await connection.fetchrow('SELECT * FROM assistants WHERE id = $1', assistant_id))


async def add_assistant(user_id: int, is_personal: bool, token: str, name: str, start_text: str, model: str,
                        instruction: str, username: str) -> int:
    async with dp.db_pool.acquire() as connection:
        return (await connection.fetch('INSERT INTO assistants(user_id, is_personal, token, name, start_text, model, '
                                       'instruction, username) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id',
                                       user_id, is_personal, token, name, start_text, model, instruction,
                                       username))[0][0]


async def update_assistant(assistant_id: int, data: dict):
    async with dp.db_pool.acquire() as connection:
        for key in data:
            await connection.execute(f'UPDATE assistants SET {key} = $1 WHERE id = $2', data[key], assistant_id)


async def delete_assistant(assistant_id: int):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('DELETE FROM assistants WHERE id = $1', assistant_id)


async def get_documents(assistant_id: int) -> list:
    async with dp.db_pool.acquire() as connection:
        data = await connection.fetch('SELECT * FROM documents WHERE assistant_id = $1', assistant_id)
        return [dict(doc) for doc in data]


async def get_document(document_id: int) -> dict:
    async with dp.db_pool.acquire() as connection:
        return dict(await connection.fetchrow('SELECT * FROM documents WHERE id = $1', document_id))


async def add_document(assistant_id: int, file_name: str):
    async with dp.db_pool.acquire() as connection:
        return (await connection.fetch('INSERT INTO documents(assistant_id, file_name) VALUES ($1, $2) RETURNING id',
                                       assistant_id, file_name))[0][0]


async def delete_document(document_id: int):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('DELETE FROM documents WHERE id = $1', document_id)

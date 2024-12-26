import os
import asyncpg
from core.assistant.internal_core.config import dp


async def get_db_pool():
    db_pool = await asyncpg.create_pool(host=os.environ['DB_HOST'],
                                        database=os.environ['DB_NAME'],
                                        user=os.environ['DB_USER'],
                                        password=os.environ['DB_PASSWORD'])
    return db_pool


async def add_user(user_id: int):
    async with dp.db_pool.acquire() as connection:
        await connection.execute('INSERT INTO users(id) VALUES ($1)', user_id)


async def get_users(user_id=None):
    async with dp.db_pool.acquire() as connection:
        if user_id is None:
            return dict(await connection.fetchrow('SELECT * FROM users'))
        else:
            return list(map(dict, list(await connection.fetchrow('SELECT * FROM users WHERE id = $1', user_id))))


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
        # assistant['is_free'] = 'gpt' not in assistant["model"].lower()
        return assistant


async def add_assistant(user_id: int, token: str):
    async with dp.db_pool.acquire() as connection:
        return (await connection.fetch('INSERT INTO assistants(user_id, token, name) VALUES ($1, $2, $3) RETURNING id',
                                       user_id, token, 'Ассистент'))[0][0]


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

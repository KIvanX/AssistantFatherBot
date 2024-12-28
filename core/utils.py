import asyncio
import logging
import os
import signal
import subprocess

import dotenv
from aiogram import types, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.config import dp
from core.assistant.internal_core.assistant import init_assistant


async def del_message(call: types.CallbackQuery):
    try:
        await call.message.delete()
    finally:
        pass


async def check_token(message: types.Message):
    try:
        bot_1 = Bot(message.text)
        info = await bot_1.get_me()
        return info
    except:
        await message.delete()
        keyboard = InlineKeyboardBuilder()
        keyboard.row(types.InlineKeyboardButton(text='ОК', callback_data='del'))
        await message.answer('Невалидный токен!', reply_markup=keyboard.as_markup())
        return False


async def start_assistant(assistant_id: int):
    assistant = await database.get_assistant(assistant_id)

    logging.warning(f'Start assistant {assistant_id}')
    dotenv.set_key('core/assistant/.env', "ASSISTANT_ID", str(assistant['id']))
    process = subprocess.Popen(["venv/bin/python", "core/assistant/main.py"])
    await database.update_assistant(assistant['id'], {'pid': process.pid, 'status': 'init'})


async def restart_working_assistant(assistant_id: int):
    assistant = await database.get_assistant(assistant_id)
    if assistant['pid']:
        try:
            os.kill(assistant['pid'], signal.SIGTERM)
        except:
            await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})
            return 0

        await start_assistant(assistant_id)
    elif assistant['is_personal']:
        asyncio.create_task(init_personal_assistant(assistant))


async def check_assistant_status(assistant: dict):
    if assistant['pid']:
        try:
            os.kill(assistant['pid'], 0)
            return True
        except OSError:
            await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})
            return False
    return False


async def init_personal_assistant(assistant: dict):
    await database.update_assistant(assistant['id'], {'status': 'init'})
    chat_model, vector_db = await init_assistant({'database': database, 'assistant': assistant})
    dp.personal_chat_model[assistant['user_id']] = chat_model
    dp.personal_vector_db[assistant['user_id']] = vector_db
    await database.update_assistant(assistant['id'], {'status': 'working'})

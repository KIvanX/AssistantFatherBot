import os
import subprocess

from aiogram import types, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.config import dp


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


async def restart_assistant(assistant_id: int):
    process = dp.assistants.get(assistant_id)
    if process:
        process.terminate()
        process.wait()
        dp.assistants[assistant_id] = subprocess.Popen([".venv/bin/python", "core/assistant/main.py"])


async def check_assistant_status(assistant: dict):
    if assistant['pid']:
        try:
            os.kill(assistant['pid'], 0)
            return True
        except OSError:
            await database.update_assistant(assistant['id'], {'pid': None})
            return False
    return False

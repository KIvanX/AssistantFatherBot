from aiogram import types, F
from datetime import datetime
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import config
from core.config import dp, bot


@dp.message(Command('logs'))
async def get_logs(message: types.Message):
    if message.chat.id == 1914011859:
        await message.delete()
        keyboard = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text='ОК', callback_data='del'))
        await bot.send_document(message.chat.id, FSInputFile('core/static/logs.log'), reply_markup=keyboard.as_markup())

        with open('core/static/logs.log', 'w') as file:
            file.write(str(datetime.now()) + '\n')

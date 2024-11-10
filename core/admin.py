from aiogram import types, F
from datetime import datetime
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import config
from core.config import dp, users, bot


@dp.message(Command('logs'))
async def get_logs(message: types.Message):
    if message.chat.id == 1914011859:
        await message.delete()
        keyboard = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text='ОК', callback_data='del'))
        await bot.send_document(message.chat.id, FSInputFile('core/static/logs.log'), reply_markup=keyboard.as_markup())

        with open('core/static/logs.log', 'w') as file:
            file.write(str(datetime.now()) + '\n')


@dp.callback_query(F.data == 'del')
async def del_message(call: types.CallbackQuery):
    try:
        await call.message.delete()
    finally:
        pass


@dp.message(Command('password'))
async def get_password(message: types.Message):
    if message.chat.id == 1914011859:
        await message.answer(config.AUTH_PASSWORD)


async def get_users(call: types.CallbackQuery):
    text = f'👥 Всего пользователей: {len(users)}\n\n<b>Авторизованные пользователи</b>\n\n'
    for i, user_id in enumerate(users):
        if users[user_id].get("auth"):
            text += f'{i + 1}) {users[user_id]["name"]} ({users[user_id]["requests"]})\n'

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='Назад', callback_data='start'))
    await call.message.edit_text(text, reply_markup=keyboard.as_markup())

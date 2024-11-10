import asyncio

from aiogram import types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import middleware, database
from core.config import dp, bot


@dp.callback_query(F.data == 'start')
@dp.message(Command('start'))
async def start(data):
    message: types.Message = data.message if 'message' in dict(data) else data

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='Создать ассистента', callback_data='create_assistant'))

    ans = message.answer if 'message' not in dict(data) else message.edit_text
    await ans(f'Добро пожаловать! Здесь Вы можете создать и администрировать своих ассистентов.',
              reply_markup=keyboard.as_markup())


async def on_startup():
    dp.db_pool = await database.get_db_pool()


async def main():
    dp.update.middleware(middleware.Middleware())

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Старт"),
        types.BotCommand(command="help", description="Инструкция"),
    ])

    await dp.start_polling(bot, on_startup=on_startup)


print('Бот приступил к работе')
if __name__ == "__main__":
    asyncio.run(main())

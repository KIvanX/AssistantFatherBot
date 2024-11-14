import asyncio

from aiogram import types, F
from aiogram.filters import Command

from core import middleware, database
from core.config import dp, bot
from core.filters import SelectAssistant
from core.handlers.assistant_menu import assistant_menu
from core.handlers.basic import start
from core.utils import del_message


async def main():
    dp.db_pool = await database.get_db_pool()
    dp.update.middleware(middleware.Middleware())
    dp.message.register(start, Command('start'))
    dp.callback_query.register(assistant_menu, SelectAssistant.filter())
    dp.callback_query.register(del_message, F.data == 'del')

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Старт"),
        types.BotCommand(command="help", description="Инструкция"),
    ])

    await dp.start_polling(bot)


print('Бот приступил к работе')
if __name__ == "__main__":
    asyncio.run(main())

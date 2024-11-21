import asyncio

from aiogram import types, F
from aiogram.filters import Command

from core import middleware, database
from core.config import dp, bot
from core.filters import SelectAssistant
from core.handlers.admin import get_logs
from core.handlers.menu import assistant_menu
from core.handlers.basic import start
from core.handlers.settings import assistant_settings
from core.utils import del_message, check_assistant_status, start_assistant


async def main():
    dp.db_pool = await database.get_db_pool()
    dp.update.middleware(middleware.Middleware())
    dp.message.register(start, Command('start'))
    dp.callback_query.register(assistant_menu, SelectAssistant.filter())
    dp.callback_query.register(del_message, F.data == 'del')
    dp.callback_query.register(assistant_settings, F.data == 'assistant_settings')
    dp.message.register(get_logs, Command('logs'))

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Старт"),
    ])

    for user in await database.get_users():
        for assistant in await database.get_assistants(user['id']):
            if assistant['pid']:
                status = await check_assistant_status(assistant)
                if not status:
                    await start_assistant(assistant['id'])

    await dp.start_polling(bot)


print('Бот приступил к работе')
if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import os

import dotenv
from aiogram import types, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI

from core.assistant.internal_core.utils import init_logging
from .internal_core.middleware import TranslaterMiddleware
from .internal_core import database, admin, mailing
from .internal_core.openai_assistant import init_openai_assistant, get_openai_message
from .internal_core.assistant import init_assistant, get_message
from .internal_core.config import dp


async def start_command(message: types.Message, state: FSMContext):
    users = await database.get_assistant_users(dp.assistant['id'])
    if message.chat.id not in [user['user_id'] for user in users] and message.from_user.full_name:
        await database.add_assistant_user(message.chat.id, message.from_user.full_name, dp.assistant['id'])

    if dp.assistant["own_search"] or 'gpt' not in dp.assistant["model"].lower():
        thread = (await state.get_data()).get('thread', {})
        thread[str(message.chat.id)] = []
        await state.update_data(thread=thread)
    else:
        thread = await dp.client.beta.threads.create()
        await state.update_data(thread_id=thread.id)
    await message.answer(dp.assistant['start_text'])


@dp.my_chat_member()
async def my_chat_member(msg: types.ChatMemberUpdated):
    if msg.new_chat_member.status == 'kicked':
        await database.update_assistant_user(msg.chat.id, {'is_deleted': True})
    elif msg.new_chat_member.status == 'member':
        await database.update_assistant_user(msg.chat.id, {'is_deleted': False})


async def main():
    dotenv.load_dotenv()
    init_logging()

    dp.db_pool = await database.get_db_pool()
    dp.assistant = await database.get_assistant(int(os.environ.get('ASSISTANT_ID')))
    dp.message.register(start_command, CommandStart())
    dp.message.register(admin.admin_menu, Command('admin'))
    dp.callback_query.register(mailing.func_create_mail, F.data == 'mailing')
    dp.bot = Bot(dp.assistant['token'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.translations = await database.get_translations()
    dp.update.middleware(TranslaterMiddleware())
    dp.client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    await dp.bot.set_my_commands([types.BotCommand(command="start", description="Старт")])

    if dp.assistant["own_search"] or 'gpt' not in dp.assistant["model"].lower():
        dp.message.register(get_message, F.text[0] != '/')
        dp.chat_model, dp.vector_db = await init_assistant()
    else:
        dp.message.register(get_openai_message, F.text[0] != '/')
        dp.assistant_id = await init_openai_assistant()

    dotenv.set_key('core/assistant/.env', "ASSISTANT_ID", '')
    logging.warning(f'Assistant {dp.assistant["id"]} is ready to work!')
    await database.update_assistant(dp.assistant['id'], {'status': 'working'})
    await dp.start_polling(dp.bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import os

from aiogram import types, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI

from core import database
from core.assistant import init_assistant, get_message
from core.opensourse_assistant import get_message_opensource, init_opensource_assistant
from core.config import dp


@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    thread = await dp.client.beta.threads.create()
    dp.store = {}
    await state.update_data(thread_id=thread.id)
    await message.answer(dp.assistant['start_text'])


async def main():
    dp.db_pool = await database.get_db_pool()
    dp.assistant = await database.get_assistant(int(os.environ.get('ASSISTANT_ID')))
    dp.bot = Bot(dp.assistant['token'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

    if 'gpt' in dp.assistant["model"]:
        dp.message.register(get_message, F.text[0] != '/')
        await init_assistant()
    else:
        dp.message.register(get_message_opensource, F.text[0] != '/')
        await init_opensource_assistant()
    logging.warning(f'Assistant {dp.assistant["id"]} is ready to work!')
    await database.update_assistant(dp.assistant['id'], {'status': 'working'})
    await dp.start_polling(dp.bot)


if os.environ.get('ASSISTANT_ID'):
    asyncio.run(main())

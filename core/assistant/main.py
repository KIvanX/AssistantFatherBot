import asyncio
import logging
import sys
import os

import dotenv
from aiogram import types, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI
from .internal_core import database
from .internal_core.openai_assistant import init_openai_assistant, get_openai_message
from .internal_core.assistant import init_assistant, get_message
from .internal_core.config import dp


async def start_command(message: types.Message, state: FSMContext):
    if dp.assistant["own_search"] or 'gpt' not in dp.assistant["model"].lower():
        thread = (await state.get_data()).get('thread', {})
        thread[str(message.chat.id)] = []
        await state.update_data(thread=thread)
    else:
        thread = await dp.client.beta.threads.create()
        await state.update_data(thread_id=thread.id)
    await message.answer(dp.assistant['start_text'])


async def main():
    dotenv.load_dotenv()

    dp.db_pool = await database.get_db_pool()
    dp.assistant = await database.get_assistant(int(os.environ.get('ASSISTANT_ID')))
    dp.message.register(start_command, CommandStart())
    dp.bot = Bot(dp.assistant['token'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    if dp.assistant["own_search"] or 'gpt' not in dp.assistant["model"].lower():
        dp.message.register(get_message, F.text[0] != '/')
        dp.chat_model, dp.vector_db = await init_assistant()
    else:
        dp.client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        dp.message.register(get_openai_message, F.text[0] != '/')
        await init_openai_assistant()

    logging.warning(f'Assistant {dp.assistant["id"]} is ready to work!')
    await database.update_assistant(dp.assistant['id'], {'status': 'working'})
    await dp.start_polling(dp.bot)


if __name__ == "__main__":
    asyncio.run(main())

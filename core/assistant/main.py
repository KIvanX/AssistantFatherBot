import asyncio
import os

from aiogram import types, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI

from core import database
from core.assistant import get_text, init_assistant
from core.config import dp


@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    thread = await dp.client.beta.threads.create()
    await state.update_data(thread_id=thread.id)
    await message.answer(f"Привет! Я <b>{dp.assistant['name']}</b>! Чем могу помочь?")


async def main():
    dp.db_pool = await database.get_db_pool()
    dp.assistant = await database.get_assistant(int(os.environ.get('ASSISTANT_ID')))
    dp.bot = Bot(dp.assistant['token'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.client = AsyncOpenAI(api_key=os.environ.get('OPEN_AI_KEY'))
    dp.message.register(get_text, F.text[0] != '/')

    await init_assistant()
    await dp.start_polling(dp.bot)


if os.environ.get('ASSISTANT_ID'):
    asyncio.run(main())

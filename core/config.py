import asyncio
import os
import dotenv
import yookassa
from aiogram import Dispatcher, Bot
import logging
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

commercial_models = ["gpt-4o", "gpt-4o-2024-11-20", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
                     "GigaChat", "GigaChat-Pro", "GigaChat-Max", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest",
                     "claude-3-opus-latest"]
free_models = ['qwen-2.5-32b', 'deepseek-r1-distill-qwen-32b', 'gemma2-9b-it', 'deepseek-r1-distill-llama-70b', 'llama-3.3-70b-versatile',
               'llama-3.1-8b-instant', 'llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768']

dotenv.load_dotenv()

bot = Bot(os.environ.get('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = RedisStorage.from_url('redis://localhost:6379/5')
loop = asyncio.get_event_loop()
dp = Dispatcher(storage=storage, loop=loop)
yookassa.Configuration.account_id = os.environ['UKASSA_SHOP_ID']
yookassa.Configuration.secret_key = os.environ['UKASSA_SECRET_KEY']

if os.environ.get('DEBUG', '').lower() == 'false':
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.WARNING, filename="core/static/logs.log", filemode="w",
                        format="%(asctime)s %(levelname)s %(message)s\n" + '_' * 100)

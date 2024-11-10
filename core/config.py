
import os
import aioredis
import dotenv
from aiogram import Dispatcher, Bot
import logging
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.enums import ParseMode
from openai import OpenAI

dotenv.load_dotenv()

bot = Bot(os.environ.get('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
redis = aioredis.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=RedisStorage(redis))
client = OpenAI(api_key=os.environ.get('OPEN_AI_KEY'))


if os.environ.get('DEBUG', '').lower() == 'false':
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.WARNING, filename="core/static/logs.log", filemode="w",
                        format="%(asctime)s %(levelname)s %(message)s\n" + '_' * 100)

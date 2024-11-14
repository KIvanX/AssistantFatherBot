
import os
import dotenv
from aiogram import Dispatcher, Bot
import logging
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

dotenv.load_dotenv()

bot = Bot(os.environ.get('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)


if os.environ.get('DEBUG', '').lower() == 'false':
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.WARNING, filename="core/static/logs.log", filemode="w",
                        format="%(asctime)s %(levelname)s %(message)s\n" + '_' * 100)

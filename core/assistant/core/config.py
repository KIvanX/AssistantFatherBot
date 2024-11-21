import logging
import os

import dotenv
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

dotenv.load_dotenv()
storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)

if os.environ.get('DEBUG', '').lower() == 'false':
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.WARNING, filename="core/static/logs.log", filemode="a",
                        format=f"ASSISTANT {os.environ.get('ASSISTANT_ID')} %(asctime)s %(levelname)s "
                               f"%(message)s\n" + '_' * 100)
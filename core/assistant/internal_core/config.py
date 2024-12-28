import logging
import os
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage


DEBUG = os.environ.get('DEBUG', '').lower() != 'false'
storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)

if not DEBUG:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    path = f"core/assistant/internal_core/static/{os.environ['ASSISTANT_ID']}/logs.log"
    logging.basicConfig(level=logging.WARNING, filename=path, filemode="a",
                        format=f"ASSISTANT {os.environ.get('ASSISTANT_ID')} %(asctime)s %(levelname)s "
                               f"%(message)s\n" + '_' * 100)

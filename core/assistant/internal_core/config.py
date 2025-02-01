import logging
import os
from aiogram import Dispatcher
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.redis import RedisStorage


help_info = {'ru': 'https://telegra.ph/Spravka-bota-Sozdatel-assistentov-01-24',
             'en': 'https://telegra.ph/Bot-Help-Assistant-Creator-01-24',
             'fr': 'https://telegra.ph/Créateur-dAssistants-01-24-2',
             'de': 'https://telegra.ph/Einführung-01-24',
             'ja': 'https://telegra.ph/はじめに-01-24',
             'it': 'https://telegra.ph/Creatore-di-Assistenti-01-24',
             'ar': 'https://telegra.ph/منشئ-المساعدين-01-24',
             'zh': 'https://telegra.ph/创建助手机器人-01-24'}


DEBUG = os.environ.get('DEBUG', '').lower() != 'false'
storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)


if not DEBUG and os.environ.get('ASSISTANT_ID'):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    print('init')
    logging.basicConfig(level=logging.WARNING, filename=f"core/static/logs.log", filemode="a",
                        format=f"ASSISTANT {os.environ.get('ASSISTANT_ID')} %(asctime)s %(levelname)s "
                               f"%(message)s\n" + '_' * 100)

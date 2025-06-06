import logging
import os

import dotenv
from aiogram import Dispatcher
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.redis import RedisStorage


help_info = {'ru': 'https://telegra.ph/new-05-31-12',
             'en': 'https://telegra.ph/Bot-Help-Assistant-Creator-01-24',
             'fr': 'https://telegra.ph/Créateur-dAssistants-01-24-2',
             'de': 'https://telegra.ph/Einführung-01-24',
             'ja': 'https://telegra.ph/はじめに-01-24',
             'it': 'https://telegra.ph/Creatore-di-Assistenti-01-24',
             'ar': 'https://telegra.ph/منشئ-المساعدين-01-24',
             'zh': 'https://telegra.ph/创建助手机器人-01-24'}


storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)

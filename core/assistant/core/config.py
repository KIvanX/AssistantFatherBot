
import dotenv
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

dotenv.load_dotenv()
storage = RedisStorage.from_url('redis://localhost:6379/5')
dp = Dispatcher(storage=storage)

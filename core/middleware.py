from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram import types

from core import config


class Middleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:

        return await handler(event, data)

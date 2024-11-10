from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram import types

from core import config
from core.utils import get_user, auth_user


class Middleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if event.message or event.callback_query:
            message = event.message if event.message else event.callback_query.message
            if message.text == config.AUTH_PASSWORD:
                return await auth_user(message)

            user = await get_user(message)
            if not user:
                return 0
            data['user'] = user

        return await handler(event, data)

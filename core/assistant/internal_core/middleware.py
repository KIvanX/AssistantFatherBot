
import json
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from . import database
from .config import dp
from ...config import BASIC_LLM


class TranslaterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        language = 'ru'
        if event.callback_query:
            language = (await database.get_users(event.callback_query.message.chat.id)).get('language', 'ru')
        elif event.message:
            language = (await database.get_users(event.message.chat.id)).get('language', 'ru')

        data['T'] = lambda ru_text, *args: translater(ru_text, language or 'ru', *args)
        return await handler(event, data)


async def translater(ru_text, language, *args):
    if ru_text not in dp.translations:
        dp.translations[ru_text] = await load_translate(ru_text)
    tr = dp.translations[ru_text][language]
    for i in range(len(args), 0, -1):
        tr = tr.replace(f'_{i}', str(args[i - 1]))
    return tr


async def load_translate(ru_text):
    tr = (await dp.client.chat.completions.create(
        model=BASIC_LLM,
        messages=[{"role": "system", "content": 'Переведи текст на все нужные языки и верни ответ в виде json, '
                                                'например: {"ru": "привет", "en": "hello", "fr": "bonjour", '
                                                '"de": "hallo", "ja": "こんにちは", "it": "ciao", '
                                                '"ar": "مرحبا",  "zh": "你好"}. Ничего лишнего не добавляй, '
                                                'только json с переводами. Русский текст оставь как есть. \n\n'
                                                'Текст: «' + ru_text + '».'}]
    )).choices[0].message.content

    tr = tr.replace('```json\n', '').replace('```', '')
    try:
        tr_json = json.loads(tr)
    except:
        input(tr)
        tr_json = {}
    with open('core/static/translations.json', 'w') as f:
        f.write(ru_text + '\n\n' + tr)
    await database.add_translation(tr_json)
    return tr_json

import asyncio
import html
import json
import random

from aiogram import types
from core import config
from core.config import users, bot, prices
from PIL import Image
from pylatexenc.latex2text import LatexNodes2Text


async def get_user(message, auth=False):
    if str(message.chat.id) not in users:
        name = (message.chat.first_name or '_') + ' ' + (message.chat.last_name or '')
        users[str(message.chat.id)] = {'chat': [], 'chat_lens': 5, 'name': name, 'model': 'GPT-4o',
                                       'requests': 0}
        save_data()

    if not auth and 'auth' not in users[str(message.chat.id)]:
        await message.answer('Перед использованием этого бота требуется авторизация. '
                             'Если Вам не выдали пароль, можете использовать аналогичного бота '
                             '<a href="https://t.me/OpenAI_company_chatGPT_bot">тут</a>.'
                             '\n\nВведите пароль:')
        return {}

    user = users[str(message.chat.id)]
    user['chat'] = user['chat'][-user['chat_lens'] * 2:] if user['chat_lens'] > 0 else []
    return user


def get_command_parameters(text):
    params = {}
    for p in ['m', 's', 'q', 'v', 'n']:
        if f'-{p} ' in text:
            value = text.split(f'-{p} ')[1].split(' ')[0]
            params[p] = value
            text = text.replace(f'-{p} ' + value + ' ', '')

    return text, params


def save_data():
    with open('core/static/data.conf', 'w') as file:
        json.dump({'users': users, 'prices': prices}, file, indent=4, ensure_ascii=False)


def jpg_to_png(path):
    img = Image.open(path)
    img.save(path[:path.rfind('.')] + '.png')


def jpg_to_png_alpha(path):
    img = Image.open(path).convert("RGBA")
    datas = img.getdata()

    newData = []
    for item in datas:
        if item[0] == 255 and item[1] == 255 and item[2] == 255:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)

    img.putdata(newData)
    img.save(path[:path.rfind('.')] + '.png')


def get_help_text():
    return ('<b>Инструкция</b>\n\n'
            'При текстовом сообщении отвечает выбранная в "/start - <i>Языковая модель</i>" модель.\n\n'
            'При отправки голосового сообщения генерируется транскрипция моделью <i>whisper-1</i>.\n\n'
            'При отправки картинки без текста генерируется ее вариант моделью <i>dall-e-2</i>, '
            'в ином случае на нее отвечает языковая модель (Только <i>GPT-4o</i> или <i>GPT-4o-mini</i>).\n\n'
            'Генерация речи из текста по команде /speech.\n\n'
            'Генерация изображения по команде /image.\n\n'
            'Команда /file_search используется для создания ассистента со знаниями из документа.\n\n'
            'Команда /code_interpreter используется для создания ассистента для анализа файла.\n\n'
            # 'Изменение изображения по команде /edits.\n\n'
            'Команда /embedding позволит получить сходство двух текстов по смыслу.\n\n'
            'Команда /context используется для задания количества сообщений, которые запоминает модель.\n\n'
            'Команда /delete_context удалят все сохраненные моделью сообщения, '
            'что позволит начать новый диалог.')


async def send_blocks_text(s, prev_s, mes, offset, parse_mode):
    if len(s[offset:]) > 4096:
        offset = len(prev_s)
        try:
            await mes.edit_text(prev_s, parse_mode='Markdown')
        except Exception:
            pass
        mes = await bot.send_message(mes.chat.id, '...')

    try:
        await mes.edit_text(s[offset:], parse_mode=parse_mode)
    except Exception:
        await asyncio.sleep(1)
        await mes.edit_text(html.escape(s[offset:]), parse_mode=None)

    return mes, offset


async def auth_user(message: types.Message):
    user = await get_user(message, auth=True)
    user['auth'] = True
    save_data()
    simbols = list(range(ord('a'), ord('z') + 1)) + list(range(ord('A'), ord('Z') + 1)) + 2 * list(range(48, 58))
    config.AUTH_PASSWORD = ''.join([chr(random.choice(simbols)) for _ in range(6)])
    await message.answer('Авторизация прошла успешно! Нажмите /start')


def latex_to_unicode(s: str) -> str:
    if "```" not in s:
        for f, t in {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
                     "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "∘": "°",
                     "=": "⁼", "(": "⁽", ")": "⁾", "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᶢ",
                     "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ",
                     "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
                     "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ", "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ",
                     "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ", "T": "ᵀ", "U": "ᵁ", "W": "ᵂ"}.items():
            s = s.replace('^' + f, t)

        for f, t in {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
                     "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "i": "ᵢ", "o": "ₒ",
                     "r": "ᵣ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ"}.items():
            s = s.replace('_' + f, t)

    def convert(s1: str) -> str:
        return LatexNodes2Text().latex_to_text(s1)

    while r'\(' in s:
        i = s.find(r'\(')
        j = i + s[i:].find(r'\)') + 2
        s = s[:i] + convert(s[i: j]) + s[j:]

    while r'\]' in s:
        j = s.find(r'\]') + 2
        i = s[:j].rfind(r'[') if r'\[' not in s[:j] else s[:j].rfind(r'\[')
        s = s[:i] + convert(s[i: j]) + s[j:]

    return s

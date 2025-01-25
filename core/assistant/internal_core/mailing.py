import asyncio
import logging
import time

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.assistant.internal_core import database
from core.assistant.internal_core.config import dp


class MailStates(StatesGroup):
    MediaState = State()
    TextState = State()
    KeyboardState = State()
    CheckState = State()


@dp.callback_query(F.data == 'back', MailStates.TextState)
async def func_create_mail(call: types.CallbackQuery, state: FSMContext, T):
    await state.set_state(MailStates.MediaState)
    await state.update_data(message_id=call.message.message_id)
    keyboard = InlineKeyboardBuilder().add(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'),
                                                                      callback_data='admin'))
    await call.message.edit_text(await T('Отправь мне фото/гиф/видео/текст или готовый пост'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'back', MailStates.KeyboardState)
@dp.message(MailStates.MediaState, F.text | F.photo | F.animation | F.video)
async def func_check_mail_file(data, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data

    if isinstance(data, types.Message):
        text = message.caption or ''
        keyboard = message.reply_markup.inline_keyboard if 'reply_markup' in message else []
        file_type = message.content_type.split('.')[-1].lower()
        if file_type != 'text':
            mes = message.model_dump()
            file_id = mes[file_type]['file_id'] if file_type != 'photo' else mes[file_type][-1]['file_id']
            await state.update_data(text=text, keyboard=keyboard, file_type=file_type, file_id=file_id)
        else:
            await state.update_data(text=message.html_text, keyboard=keyboard, file_type=file_type, file_id=0)
        await message.delete()
    else:
        text = (await state.get_data())['text']

    await state.set_state(MailStates.TextState)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text=await T('Пропустить'), callback_data='mail_keyboard'))
    keyboard.add(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='back'))
    await dp.bot.edit_message_text(await T(f'Если хочешь {"изменить" if text else "добавить"} текст, отправь его сюда'),
                                   chat_id=message.chat.id, message_id=(await state.get_data())['message_id'],
                                   reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', MailStates.TextState)
async def func_edit_text(message: types.Message, state: FSMContext, T):
    await state.update_data(text=message.html_text)
    await message.delete()
    await func_create_mail_keyboard(message, state, T)


@dp.callback_query(F.data == 'back', MailStates.CheckState)
@dp.callback_query(F.data == 'mail_keyboard')
async def func_create_mail_keyboard(data, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    keyboard = (await state.get_data())['keyboard']
    text = f'''
Отлично! Ты можешь {"изменить" if keyboard else "добавить"} кнопки.
Отправь мне список URL-кнопок в одном сообщении. Следуй этому формату:

Кнопка 1 - https://example1.com
Кнопка 2 - https://example2.com

Используй разделитель |, чтобы установить кнопки в одну строчку. Пример:

Кнопка 1 - https://example1.com | Кнопка 2 - https://example2.com
Кнопка 3 - https://example3.com | Кнопка 4 - https://example4.com'''
    text = await T(text)
    await state.set_state(MailStates.KeyboardState)
    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text=await T('Пропустить'), callback_data='mail_check'))
    keyboard.add(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='back'))
    if isinstance(data, types.CallbackQuery) and data.data == 'back':
        call: types.CallbackQuery = data
        await call.message.delete()
        mes = await call.message.answer(text, reply_markup=keyboard.as_markup())
        await state.update_data(message_id=mes.message_id)
    else:
        await dp.bot.edit_message_text(text, chat_id=message.chat.id, message_id=(await state.get_data())['message_id'],
                                       reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', MailStates.KeyboardState)
async def func_edit_keyboard(message: types.Message, state: FSMContext, T):
    keyboard = []
    for line in message.text.split('\n'):
        but_line = [{'text': buts.split('-')[0], 'url': buts.split('-')[1].strip()} for buts in line.split('|')]
        keyboard.append(but_line)

    await state.update_data(keyboard=keyboard)
    await message.delete()
    await func_finish_mail_check(message, state, T)


@dp.callback_query(F.data == 'mail_check')
async def func_finish_mail_check(message, state: FSMContext, T):
    call_data, message = (message.data, message.message) if isinstance(message, types.CallbackQuery) else ('', message)

    mail = (await state.get_data())
    keyboard = InlineKeyboardBuilder()
    for line in mail['keyboard']:
        keyboard.row(*[types.InlineKeyboardButton(text=but['text'], url=but['url']) for but in line])
    keyboard.row(types.InlineKeyboardButton(text=f'📣 ' + await T('Запустить рассылку'), callback_data='start_mail'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='back'))

    await state.set_state(MailStates.CheckState)

    await dp.bot.delete_message(message.chat.id, (await state.get_data())['message_id'])
    if mail['file_type'] == 'photo':
        await dp.bot.send_photo(message.chat.id, mail['file_id'], caption=mail['text'],
                                reply_markup=keyboard.as_markup())
    elif mail['file_type'] == 'animation':
        await dp.bot.send_animation(message.chat.id, mail['file_id'], caption=mail['text'],
                                    reply_markup=keyboard.as_markup())
    elif mail['file_type'] == 'video':
        await dp.bot.send_video(message.chat.id, mail['file_id'], caption=mail['text'],
                                reply_markup=keyboard.as_markup())
    else:
        await dp.bot.send_message(message.chat.id, mail['text'], reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data == 'start_mail')
async def func_start_mail(call: types.CallbackQuery, state: FSMContext, T):
    mail = (await state.get_data())

    await call.message.delete()
    message = (await call.message.answer(await T('Отправлено') + ' 0%'))

    keyboard = InlineKeyboardBuilder()
    for line in mail['keyboard']:
        keyboard.row(*[types.InlineKeyboardButton(text=but['text'], url=but['url']) for but in line])

    prev = (time.time(), 0)
    users = await database.get_users()
    for i, user in enumerate(users):
        try:
            if mail['file_type'] == 'photo':
                await dp.bot.send_photo(user['id'], mail['file_id'], caption=mail['text'],
                                        reply_markup=keyboard.as_markup())
            elif mail['file_type'] == 'animation':
                await dp.bot.send_animation(user['id'], mail['file_id'], caption=mail['text'],
                                            reply_markup=keyboard.as_markup())
            elif mail['file_type'] == 'video':
                await dp.bot.send_video(user['id'], mail['file_id'], caption=mail['text'],
                                        reply_markup=keyboard.as_markup())
            else:
                await dp.bot.send_message(user['id'], mail['text'], reply_markup=keyboard.as_markup())

            if time.time() - prev[0] > 1 and round(i / len(users) * 100, 2) != prev[1]:
                prev = (time.time(), round(i / len(users) * 100, 2))
                await message.edit_text(await T('Отправлено') + f' {prev[1]}%')

            await asyncio.sleep(0.05)
        except Exception as e:
            logging.error('Mailing error: ' + str(e))

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='⬅️ ' + await T('Меню'), callback_data='admin'))
    await message.edit_text(f'✅ ' + await T('Рассылка завершена'), reply_markup=keyboard.as_markup())

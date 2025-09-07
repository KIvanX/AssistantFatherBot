import json
import logging
import os

from aiogram import F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.assistant.internal_core.config import help_info
from core.config import dp, bot, BASIC_LLM
from core.filters import SelectAssistant
from core.handlers.menu import assistant_menu
from core.middleware import translater
from core.states import CreateAssistantStates, BaseAssistantStates
from core.static.prompts import auto_create_assistant_text
from core.utils import check_token
import yookassa


@dp.callback_query(F.data == 'start')
async def start(data, state: FSMContext, T):
    message: types.Message = data.message if 'message' in dict(data) else data
    user = await database.get_users(message.chat.id)
    await state.clear()

    if not user:
        await database.add_user(message.chat.id)
        user = await database.get_users(message.chat.id)

    if not user['language']:
        keyboard = InlineKeyboardBuilder()
        for lang in [('🇷🇺 Русский', 'ru'), ('🇬🇧 English', 'en'), ('🇫🇷 Français', 'fr'), ('🇩🇪 Deutsch', 'de'),
                     ('🇯🇵 日本語', 'ja'), ('🇮🇹 Italiano', 'it'), ('🇸🇦 العربية', 'ar'), ('🇨🇳 中文', 'zh')]:
            keyboard.row(types.InlineKeyboardButton(text=lang[0], callback_data='set_' + lang[1]))
        keyboard.adjust(2, 2, 2, 2)
        return await message.answer(await T('Выберите язык'), reply_markup=keyboard.as_markup())

    keyboard = InlineKeyboardBuilder()
    for assistant in await database.get_assistants(message.chat.id):
        statuses = {'init': '🟡 ', 'working': '🟢 ', 'stopped': '🔴 '}
        keyboard.add(types.InlineKeyboardButton(text=statuses[assistant['status']] + assistant['name'],
                                                callback_data=SelectAssistant(id=assistant['id']).pack()))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='➕ ' + await T('Создать ассистента'),
                                            callback_data='create_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='❔ ' + await T('Справка'),
                                            url=help_info[user['language']]),
                 types.InlineKeyboardButton(text='💰 ' + await T('Пополнить баланс'), callback_data='top_up_balance'))
    ans = message.answer if 'message' not in dict(data) else message.edit_text
    await ans(await T('<b>Добро пожаловать!</b>\n\nЗдесь Вы можете создать и администрировать своих ассистентов.\n\n'
                      '<b>Ассистент</b> - это бот, который поможет Вам в общении с клиентами\n\n'
                      'Баланс: ') + str(round(user["balance"], 2)) + '₽',
              reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['set_ru', 'set_en', 'set_it', 'set_fr', 'set_de', 'set_ja', 'set_zh', 'set_ar']))
async def set_language(call: types.CallbackQuery, state: FSMContext):
    await database.update_user(call.message.chat.id, {'language': call.data.split('_')[1]})
    await start(call, state, lambda ru_text, *args: translater(ru_text, call.data.split('_')[1], *args))


@dp.message(Command('language'))
async def update_language(message: types.Message, state: FSMContext, T):
    await database.update_user(message.chat.id, {'language': ''})
    await start(message, state, T)


@dp.callback_query(F.data == 'top_up_balance')
async def top_up_balance(call: types.CallbackQuery, state: FSMContext, T):
    await state.set_state(BaseAssistantStates.top_up_balance)
    await state.update_data(message_id=call.message.message_id)

    keyboard = InlineKeyboardBuilder()
    for k in [30, 100, 200, 300, 500, 1000]:
        keyboard.add(types.InlineKeyboardButton(text=str(k) + '₽', callback_data='pay_' + str(k)))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='start'))
    keyboard.adjust(3, 3, 1)

    await call.message.edit_text(await T('Выберите сумму пополнения или введите свою'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['pay_30', 'pay_100', 'pay_200', 'pay_300', 'pay_500', 'pay_1000']),
                   BaseAssistantStates.top_up_balance)
@dp.message(F.text.isdigit(), BaseAssistantStates.top_up_balance)
async def top_up_balance(data, state: FSMContext, T):
    message: types.Message = data.message if 'message' in dict(data) else data
    await state.set_state()

    if isinstance(data, types.Message):
        amount = int(data.text)
        await message.delete()
    else:
        amount = int(data.data.split('_')[1])

    payment = yookassa.Payment.create({
        "amount": {"value": amount, "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/assistants_father_bot"},
        "capture": True,
        "payment_method_data": {"type": "bank_card"},
        "description": await T('Пополнение баланса на') + f' {amount}₽'
    })

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=await T('Оплачено'), callback_data='check_payment'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='top_up_balance'))

    await state.update_data(amount=amount, payment_id=payment.id)
    mes_id = (await state.get_data()).get('message_id')
    await bot.edit_message_text(await T(f'Перейдите по <a href="_1">ссылке</a> для оплаты',
                                        payment.confirmation.confirmation_url),
                                chat_id=message.chat.id, message_id=mes_id, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'check_payment')
async def check_payment(call: types.CallbackQuery, state: FSMContext, T):
    state_data = await state.get_data()
    payment = yookassa.Payment.find_one(state_data['payment_id'])

    if payment.status == 'succeeded':
        amount = (await state.get_data()).get('amount')
        user = await database.get_users(call.message.chat.id)
        await database.update_user(call.message.chat.id, {'balance': user['balance'] + amount})
        keyboard = InlineKeyboardBuilder()
        keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))
        await call.message.edit_text(f'✅ ' + await T('Баланс пополнен на') + f' {amount}₽',
                                     reply_markup=keyboard.as_markup())
    else:
        await call.answer(await T('Оплата еще не прошла'))


@dp.callback_query(F.data == 'create_assistant')
async def create_assistant(data, state: FSMContext, T):
    message: types.Message = data.message if 'message' in dict(data) else data
    await state.set_state(CreateAssistantStates.token)
    await state.update_data(message_id=message.message_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🤖 ' + await T('Автоматическое создание ассистента'),
                                            callback_data='auto_create_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='👤 ' + await T('Личный ассистент'),
                                            callback_data='personal_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='start'))

    await message.edit_text('📝 ' + await T(f'Введите токен Вашего бота\n\nТокен можно получить в @BotFather\n\n'
                                           f'<b>Личный ассистент</b> - ассистент, который будет работать только в этом '
                                           f'чате и доступ к нему будет только у Вас.'),
                            reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'auto_create_assistant', CreateAssistantStates.token)
async def auto_create_assistant(call: types.CallbackQuery, state: FSMContext, T):
    await state.set_state(BaseAssistantStates.auto_create)
    await state.update_data(message_id=call.message.message_id)
    user = await database.get_users(call.message.chat.id)
    system = auto_create_assistant_text.replace('_LANGUAGE_', user['language'])
    mes = (await dp.client.chat.completions.create(
        model=BASIC_LLM,
        messages=[{"role": "system", "content": system}]
    )).choices[0].message.content
    await state.update_data(chat=[{"role": "system", "content": system},
                                  {"role": "assistant", "content": mes}])
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))
    await call.message.edit_text(mes, reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', BaseAssistantStates.auto_create)
async def auto_create_assistant_step(message: types.Message, state: FSMContext, T):
    message_id = (await state.get_data()).get('message_id')
    await bot.edit_message_text(await T('Пожалуйста, подождите...'), chat_id=message.chat.id, message_id=message_id)

    chat = (await state.get_data()).get('chat', [])
    mes = (await dp.client.chat.completions.create(
        model=BASIC_LLM,
        messages=chat + [{"role": "user", "content": message.text}]
    )).choices[0].message.content
    await state.update_data(chat=chat + [{"role": "user", "content": message.text},
                                         {"role": "assistant", "content": mes}])

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))

    if '<START>' in mes and '<END>' in mes:
        info = json.loads(mes.split('<START>')[1].split('<END>')[0])
        if not info['is_personal']:
            try:
                bot_1 = Bot(info['token'])
                info['username'] = (await bot_1.get_me()).username
            except:
                return await message.answer(await T('Невалидный токен!'), reply_markup=keyboard.as_markup())

            a_id = await database.add_assistant(message.chat.id, False, info['token'], info['name'],
                                                info['start_text'], info['model'], info['instruction'],
                                                info['username'])
        else:
            a_id = await database.add_assistant(message.chat.id, True, '', info['name'],
                                                info['start_text'], info['model'], info['instruction'], '')

        os.makedirs(f"core/assistant/internal_core/static/{a_id}", exist_ok=True)

        await state.set_state()
        await message.delete()
        return await assistant_menu(message, SelectAssistant(id=a_id), state, T)

    await message.delete()
    await bot.edit_message_text(mes, chat_id=message.chat.id, message_id=message_id, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'personal_assistant', CreateAssistantStates.token)
async def personal_assistant(call: types.CallbackQuery, state: FSMContext, T):
    assistant_names = [a['name'] for a in await database.get_assistants(call.message.chat.id)]
    la = await T('Личный ассистент')
    name = f'{la} {[i for i in range(1, 1000) if f"{la} {i}" not in assistant_names][0]}'
    a_id = await database.add_assistant(call.message.chat.id, True, '', name,
                                        await T('Привет! Чем могу помочь?'), BASIC_LLM, '', '')

    os.makedirs(f"core/assistant/internal_core/static/{a_id}", exist_ok=True)
    await state.set_state()
    await assistant_menu(call, SelectAssistant(id=a_id), state, T)


@dp.message(F.text[0] != '/', CreateAssistantStates.token)
async def create_assistant_commit(message: types.Message, state: FSMContext, T):
    info = await check_token(message)
    if not info:
        return 0

    a_id = await database.add_assistant(message.chat.id, False, message.text, info.first_name,
                                        await T('Привет! Чем могу помочь?'), BASIC_LLM, '', info.username)

    os.makedirs(f"core/assistant/internal_core/static/{a_id}", exist_ok=True)
    await state.set_state()
    await message.delete()
    await assistant_menu(message, SelectAssistant(id=a_id), state, T)

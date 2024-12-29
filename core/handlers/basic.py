import json
import os

from aiogram import F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

from core import database
from core.config import dp, bot
from core.filters import SelectAssistant
from core.handlers.menu import assistant_menu
from core.states import CreateAssistantStates, BaseAssistantStates
from core.static.prompts import auto_create_assistant_text
from core.utils import check_token
import yookassa


@dp.callback_query(F.data == 'start')
async def start(data, state: FSMContext):
    message: types.Message = data.message if 'message' in dict(data) else data
    user = await database.get_users(message.chat.id)
    await state.clear()

    if not user:
        await database.add_user(message.chat.id)
        user = await database.get_users(message.chat.id)

    keyboard = InlineKeyboardBuilder()
    for assistant in await database.get_assistants(message.chat.id):
        statuses = {'init': '🟡 ', 'working': '🟢 ', 'stopped': '🔴 '}
        keyboard.add(types.InlineKeyboardButton(text=statuses[assistant['status']] + assistant['name'],
                                                callback_data=SelectAssistant(id=assistant['id']).pack()))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='➕ Создать ассистента', callback_data='create_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='💰 Пополнить баланс', callback_data='top_up_balance'))
    ans = message.answer if 'message' not in dict(data) else message.edit_text
    await ans(f'<b>Добро пожаловать!</b>\n\nЗдесь Вы можете создать и администрировать своих ассистентов.\n\n'
              f'<b>Ассистент</b> - это бот, который поможет Вам в общении с клиентами\n\n'
              f'Баланс: {round(user["balance"], 2)}₽',
              reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'top_up_balance')
async def top_up_balance(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BaseAssistantStates.top_up_balance)
    await state.update_data(message_id=call.message.message_id)

    keyboard = InlineKeyboardBuilder()
    for k in [30, 100, 200, 300, 500, 1000]:
        keyboard.add(types.InlineKeyboardButton(text=str(k) + '₽', callback_data='pay_' + str(k)))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='start'))
    keyboard.adjust(3, 3, 1)

    await call.message.edit_text(f'Выберите сумму пополнения или введите свою', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['pay_30', 'pay_100', 'pay_200', 'pay_300', 'pay_500', 'pay_1000']),
                   BaseAssistantStates.top_up_balance)
@dp.message(F.text.isdigit(), BaseAssistantStates.top_up_balance)
async def top_up_balance(data, state: FSMContext):
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
        "description": f'Пополнение баланса на {amount}₽'
    })

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='Оплачено', callback_data='check_payment'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='top_up_balance'))

    await state.update_data(amount=amount, payment_id=payment.id)
    mes_id = (await state.get_data()).get('message_id')
    await bot.edit_message_text(f'Перейдите по <a href="{payment.confirmation.confirmation_url}">ссылке</a> для оплаты',
                                chat_id=message.chat.id, message_id=mes_id, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'check_payment')
async def check_payment(call: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    payment = yookassa.Payment.find_one(state_data['payment_id'])

    if payment.status == 'succeeded':
        amount = (await state.get_data()).get('amount')
        user = await database.get_users(call.message.chat.id)
        await database.update_user(call.message.chat.id, {'balance': user['balance'] + amount})
        keyboard = InlineKeyboardBuilder()
        keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))
        await call.message.edit_text(f'✅ Баланс пополнен на {amount}₽', reply_markup=keyboard.as_markup())
    else:
        await call.answer('Оплата еще не прошла')


@dp.callback_query(F.data == 'create_assistant')
async def create_assistant(data, state: FSMContext):
    message: types.Message = data.message if 'message' in dict(data) else data
    await state.set_state(CreateAssistantStates.token)
    await state.update_data(message_id=message.message_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🤖 Автоматическое создание ассистента',
                                            callback_data='auto_create_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='👤 Личный ассистент', callback_data='personal_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='start'))

    await message.edit_text(f'Введите токен Вашего бота\n\n'
                            f'Токен можно получить в @BotFather\n\n'
                            f'<b>Личный ассистент</b> - ассистент, который будет работать только в этом чате и '
                            f'доступ к нему будет только у Вас.', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'auto_create_assistant', CreateAssistantStates.token)
async def auto_create_assistant(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BaseAssistantStates.auto_create)
    await state.update_data(message_id=call.message.message_id)
    dp.client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    mes = (await dp.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": auto_create_assistant_text}]
    )).choices[0].message.content
    await state.update_data(chat=[{"role": "system", "content": auto_create_assistant_text},
                                  {"role": "assistant", "content": mes}])
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))
    await call.message.edit_text(mes, reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', BaseAssistantStates.auto_create)
async def auto_create_assistant_step(message: types.Message, state: FSMContext):
    message_id = (await state.get_data()).get('message_id')
    await bot.edit_message_text('Пожалуйста, подождите...', chat_id=message.chat.id, message_id=message_id)

    chat = (await state.get_data()).get('chat', [])
    mes = (await dp.client.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat + [{"role": "user", "content": message.text}]
    )).choices[0].message.content
    await state.update_data(chat=chat + [{"role": "user", "content": message.text},
                                         {"role": "assistant", "content": mes}])

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))

    if '<START>' in mes and '<END>' in mes:
        info = json.loads(mes.split('<START>')[1].split('<END>')[0])
        try:
            bot_1 = Bot(info['token'])
            info['username'] = (await bot_1.get_me()).username
        except:
            return await message.answer('Невалидный токен!', reply_markup=keyboard.as_markup())

        a_id = await database.add_assistant(message.chat.id, False, info['token'], info['name'],
                                            info['start_text'], info['model'], info['instruction'], info['username'])
        if not os.path.exists(f"core/assistant/internal_core/static/{a_id}"):
            os.makedirs(f"core/assistant/internal_core/static/{a_id}")

        await state.set_state()
        await message.delete()
        return await assistant_menu(message, SelectAssistant(id=a_id), state)

    await message.delete()
    await bot.edit_message_text(mes, chat_id=message.chat.id, message_id=message_id, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'personal_assistant', CreateAssistantStates.token)
async def personal_assistant(call: types.CallbackQuery, state: FSMContext):
    info = await bot.get_me()
    assistant_names = [a['name'] for a in await database.get_assistants(call.message.chat.id)]
    name = f'Личный ассистент {[i for i in range(1, 1000) if f"Личный ассистент {i}" not in assistant_names][0]}'
    a_id = await database.add_assistant(call.message.chat.id, True, '', name,
                                        'Привет! Чем могу помочь?', 'gpt-4o-mini', '', info.username)
    if not os.path.exists(f"core/assistant/internal_core/static/{a_id}"):
        os.makedirs(f"core/assistant/internal_core/static/{a_id}")

    await state.set_state()
    await assistant_menu(call, SelectAssistant(id=a_id), state)


@dp.message(F.text[0] != '/', CreateAssistantStates.token)
async def create_assistant_commit(message: types.Message, state: FSMContext):
    info = await check_token(message)
    if not info:
        return 0

    a_id = await database.add_assistant(message.chat.id, False, message.text, info.first_name,
                                        'Привет! Чем могу помочь?', 'gpt-4o-mini', '', info.username)
    if not os.path.exists(f"core/assistant/internal_core/static/{a_id}"):
        os.makedirs(f"core/assistant/internal_core/static/{a_id}")

    await state.set_state()
    await message.delete()
    await assistant_menu(message, SelectAssistant(id=a_id), state)

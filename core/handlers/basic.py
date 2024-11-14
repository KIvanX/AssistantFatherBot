from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.config import dp
from core.filters import SelectAssistant
from core.handlers.assistant_menu import assistant_menu
from core.states import CreateAssistantStates
from core.utils import check_token


@dp.callback_query(F.data == 'start')
async def start(data, state: FSMContext):
    message: types.Message = data.message if 'message' in dict(data) else data
    await state.clear()

    keyboard = InlineKeyboardBuilder()
    for assistant in await database.get_assistants(message.chat.id):
        keyboard.add(types.InlineKeyboardButton(text=assistant['name'],
                                                callback_data=SelectAssistant(id=assistant['id']).pack()))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='➕ Создать ассистента', callback_data='create_assistant'), width=1)
    ans = message.answer if 'message' not in dict(data) else message.edit_text
    await ans(f'<b>Добро пожаловать!</b>\n\nЗдесь Вы можете создать и администрировать своих ассистентов.\n\n'
              f'<b>Ассистент</b> - это бот, который поможет Вам в общении с клиентами',
              reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'create_assistant')
async def create_assistant(data, state: FSMContext):
    message: types.Message = data.message if 'message' in dict(data) else data
    await state.set_state(CreateAssistantStates.token)
    await state.update_data(message_id=message.message_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='start'))

    await message.edit_text(f'Введите токен Вашего бота\n\n'
                            f'Токен можно получить в @BotFather', reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', CreateAssistantStates.token)
async def create_assistant_commit(message: types.Message, state: FSMContext):
    info = await check_token(message)
    if not info:
        return 0

    a_id = await database.add_assistant(message.chat.id, message.text, info.first_name, info.username)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='Настройки ассистента', callback_data=SelectAssistant(id=a_id).pack()))
    keyboard.row(types.InlineKeyboardButton(text='Главное меню', callback_data='start'))

    await state.set_state()
    await message.delete()
    await assistant_menu(message, SelectAssistant(id=a_id), state)

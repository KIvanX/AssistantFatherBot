import os
import signal

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.assistant.internal_core.utils import emb_price
from core.config import dp, bot
from core.filters import SelectAssistant
from core.states import EditAssistantStates
from core.utils import restart_working_assistant, check_token, check_assistant_status


@dp.callback_query(F.data == 'assistant_settings')
async def assistant_settings(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await state.set_state()
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🔎 ' + await T('RAG система'), callback_data='rag_settings'))
    if not assistant['is_personal']:
        keyboard.row(types.InlineKeyboardButton(text='🔑 ' + await T('Изменить токен'), callback_data='edit_token'))
    keyboard.row(types.InlineKeyboardButton(text='🗑 ' + await T('Удалить ассистента'),
                                            callback_data='delete_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'),
                                            callback_data=SelectAssistant(id=assistant['id']).pack()))
    text = 'Настройки'
    await call.message.edit_text('⚙️ ' + await T(text), reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'rag_settings')
async def rag_settings(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    text = ('RAG система\n\n'
            '<b>RAG система</b> - система поиска релевантной информации в документах из "📚 База знаний"\n\n'
            '<b>Embedding модель</b> - нейросеть, которая преобразует текст документов в векторное представление\n\n'
            f'RAG система: {"<b>Встроенная</b>" if assistant["own_search"] else "<b>OpenAI (10₽/Гб)</b>"}\n'
            f'Embedding модель: _1.\n\n'
            f'{"❕ Цена указана за миллион символов текста" if assistant["own_search"] else ""}')

    keyboard = InlineKeyboardBuilder()
    if assistant['own_search']:
        for i, (model, price) in enumerate(emb_price.items()):
            short = {'jina/jina-embeddings-v2-base-en': 'Jina V2',
                     'mistral/1024__mistral-embed': 'Mistral 1024',
                     'google/768__textembedding-gecko': 'Google Gecko 768',
                     'text-embedding-3-small': 'OpenAI 3-small',
                     'text-embedding-3-large': 'OpenAI 3-large',
                     'text-embedding-ada-002': 'OpenAI ada-002'}[model]
            txt_model = ('✅ ' + short if model == assistant['emb_model'] else short) + f' - {round(price * 100, 1)}₽'
            keyboard.add(types.InlineKeyboardButton(text=txt_model, callback_data=f'change_emb_model_{i}'))
        keyboard.adjust(2)

    if 'gpt' in assistant['model'].lower() and assistant['model'] != 'gpt-4':
        change_system = '🔄 ' + await T('Использовать RAG бота') \
            if not assistant['own_search'] else '🔄 ' + await T('Использовать RAG от OpenAI')
        keyboard.row(types.InlineKeyboardButton(text=change_system, callback_data='change_RAG_system'))

    assistant["emb_model"] = 'text-embedding-3-large' if not assistant["own_search"] else assistant["emb_model"]
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='assistant_settings'))
    await call.message.edit_text('🔎 ' + await T(text, f'<b>{assistant["emb_model"]}</b>'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.startswith('change_emb_model_'))
async def change_emb_model(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    assistant['emb_model'] = list(emb_price.keys())[int(call.data.split('_')[-1])]
    await database.update_assistant(assistant['id'], {'emb_model': assistant['emb_model']})
    await restart_working_assistant(assistant['id'])
    await rag_settings(call, state, T)


@dp.callback_query(F.data == 'change_RAG_system')
async def change_RAG_system(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await database.update_assistant(assistant['id'], {'own_search': not assistant['own_search']})
    await restart_working_assistant(assistant['id'])
    await rag_settings(call, state, T)


@dp.callback_query(F.data == 'edit_token')
async def edit_token(data, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    state_data = await state.get_data()
    await state.set_state(EditAssistantStates.edit_token)
    await state.update_data(message_id=state_data.get('message_id', message.message_id))

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='assistant_settings'))

    await bot.edit_message_text(await T(f'Текущий токен: \n\n<code>_1</code>\n\n'
                                        f'Чтобы изменить токен, введите его в чат', assistant["token"]),
                                chat_id=message.chat.id, message_id=state_data.get('message_id', message.message_id),
                                reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', EditAssistantStates.edit_token)
async def edit_token_commit(message: types.Message, state: FSMContext, T):
    info = await check_token(message)
    if not info:
        return 0

    await state.set_state()
    state_data = await state.get_data()

    await database.update_assistant(state_data['assistant_id'], {'token': message.text, 'username': info.username})

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))

    await restart_working_assistant(state_data['assistant_id'])
    await message.delete()
    await bot.edit_message_text(f'✅ ' + await T('Токен успешно изменен. \n\n'
                                                f'Обновленная ссылка на чат: @_1', info.username),
                                chat_id=message.chat.id,
                                message_id=state_data.get('message_id', message.message_id),
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'delete_assistant')
async def delete_assistant_confirm(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text=await T('Да, уверен'), callback_data='delete_assistant_confirm'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='assistant_settings'))

    await call.message.edit_text(f'❗️ ' + await T('Вы уверены, что хотите удалить ассистента <b>_1</b>?\n\n'
                                                  f'Это действие нельзя будет отменить', assistant["name"]),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'delete_assistant_confirm')
async def delete_assistant(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    if await check_assistant_status(assistant):
        os.kill(assistant['pid'], signal.SIGTERM)

    await database.delete_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))

    await call.message.edit_text(f'✅ ' + await T('Ассистент удален'), reply_markup=keyboard.as_markup())

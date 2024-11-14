import os
import signal

import dotenv
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.config import dp, bot
from core.filters import DeleteDocument, SelectAssistant
from core.states import EditAssistantStates, KnowledgeBaseAssistantStates
import subprocess

from core.utils import restart_assistant, check_assistant_status


async def assistant_menu(data, callback_data: SelectAssistant, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data

    state_data = await state.get_data()
    assistant = await database.get_assistant(callback_data.id)
    assistant_status = '🔴 Остановить бота' if await check_assistant_status(assistant) else '🟢 Запустить бота'

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=assistant_status, callback_data='change_assistant_status'))
    keyboard.row(types.InlineKeyboardButton(text='📚 База знаний', callback_data='knowledge_base'))
    keyboard.row(types.InlineKeyboardButton(text='✏️ Изменить', callback_data='edit_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⚙️ Настройки', callback_data='assistant_settings'))
    keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))
    keyboard.adjust(1, 2, 1, 1)

    await state.update_data(assistant_id=callback_data.id)
    await bot.edit_message_text(f'Ассистент <b>{assistant["name"]}</b>\n\n'
                                f'Ссылка на чат с ботом: @{assistant["username"]}', chat_id=message.chat.id,
                                message_id=state_data.get('message_id', message.message_id),
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'edit_assistant')
async def edit_assistant(data, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    a_id = (await state.get_data())['assistant_id']
    await state.set_state(EditAssistantStates.edit)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='Имя', callback_data='name'))
    keyboard.add(types.InlineKeyboardButton(text='Токен', callback_data='token'))
    keyboard.add(types.InlineKeyboardButton(text='Инструкция', callback_data='instruction'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data=SelectAssistant(id=a_id).pack()))

    assistant = await database.get_assistant(a_id)
    text = (f'<b>Имя: </b>{assistant["name"]}\n\n'
            f'<b>Токен: </b>{assistant["token"]}\n\n'
            f'<b>Инструкция: </b>{assistant["instruction"]}\n\n'
            f'✏️ Выберите, что хотите изменить')
    message_id = (await state.get_data()).get('message_id', message.message_id)
    await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_id,
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['instruction', 'token', 'name']), EditAssistantStates.edit)
async def edit_assistant_parameter(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditAssistantStates.parameter)
    await state.update_data(parameter=call.data, message_id=call.message.message_id)
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    text = {'instruction': 'Инструкция: <code>' + assistant['instruction'] + '</code>',
            'token': 'Токен: <code>' + assistant['token'] + '</code>',
            'name': 'Имя ассистента: <code>' + assistant['name'] + '</code>'}[call.data]
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='edit_assistant'))

    await call.message.edit_text(text + f'\n\n✏️ Введите новое значение', reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', EditAssistantStates.parameter)
async def edit_assistant_commit(message: types.Message, state: FSMContext):
    await state.set_state()

    state_data = await state.get_data()
    await database.update_assistant(state_data['assistant_id'], {state_data['parameter']: message.text})

    await restart_assistant(state_data['assistant_id'])
    await message.delete()
    await edit_assistant(message, state)


@dp.callback_query(F.data == 'knowledge_base')
async def knowledge_base(data, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    state_data = await state.get_data()
    a_id = state_data['assistant_id']

    text = '📚 Загруженные документы\n\n'
    for doc in (await database.get_documents(a_id)):
        text += '├ <b>' + doc['file_name'] + '</b>\n'
    text = text[:text.rfind('├')] + '└' + text[text.rfind('├') + 1:] if '├' in text else text

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='➕ Добавить документ', callback_data='add_document'))
    keyboard.row(types.InlineKeyboardButton(text='➖ Удаление документов', callback_data='delete_documents'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data=SelectAssistant(id=a_id).pack()))

    await bot.edit_message_text(text, chat_id=message.chat.id,
                                message_id=state_data.get('message_id', message.message_id),
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'add_document')
async def add_document(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(KnowledgeBaseAssistantStates.add)
    await state.update_data(message_id=call.message.message_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='knowledge_base'))
    await call.message.edit_text('📚 Отправьте нужный документ', reply_markup=keyboard.as_markup())


@dp.message(F.document, KnowledgeBaseAssistantStates.add)
async def add_document_commit(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    assistant = await database.get_assistant(state_data['assistant_id'])

    path = f'core/static/{state_data["assistant_id"]}'
    if not os.path.exists(path):
        os.makedirs(path)

    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, path + '/' + message.document.file_name)
    await database.add_document(assistant['id'], message.document.file_name)

    await restart_assistant(state_data['assistant_id'])
    await message.delete()
    await knowledge_base(message, state)


@dp.callback_query(F.data == 'delete_documents')
async def delete_documents(call: types.CallbackQuery, state: FSMContext):
    a_id = (await state.get_data())['assistant_id']

    keyboard = InlineKeyboardBuilder()
    for doc in (await database.get_documents(a_id)):
        keyboard.add(types.InlineKeyboardButton(text=doc['file_name'],
                                                callback_data=DeleteDocument(id=doc['id']).pack()))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='knowledge_base'), width=1)

    await call.message.edit_text('Выберите документ, который нужно удалить', reply_markup=keyboard.as_markup())


@dp.callback_query(DeleteDocument.filter())
async def delete_documents_commit(call: types.CallbackQuery, state: FSMContext, callback_data: DeleteDocument):
    await state.set_state(KnowledgeBaseAssistantStates.add)
    await state.update_data(message_id=call.message.message_id)

    doc = await database.get_document(callback_data.id)
    await database.delete_document(doc['id'])
    if os.path.isfile('core/static/' + str(doc['assistant_id']) + '/' + doc['file_name']):
        os.remove('core/static/' + str(doc['assistant_id']) + '/' + doc['file_name'])

    await restart_assistant(doc['assistant_id'])
    await call.answer('✅ Документ удален')
    await delete_documents(call, state)


@dp.callback_query(F.data == 'change_assistant_status')
async def change_assistant_status(call: types.CallbackQuery, state: FSMContext):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    if assistant['pid']:
        try:
            os.kill(assistant['pid'], signal.SIGTERM)
        except:
            pass
        await database.update_assistant(assistant['id'], {'pid': None})
    else:
        os.environ['ASSISTANT_ID'] = str(assistant['id'])
        dotenv.set_key('core/assistant/.env', "ASSISTANT_ID", os.environ["ASSISTANT_ID"])
        process = subprocess.Popen(["venv/bin/python", "core/assistant/main.py"])
        await database.update_assistant(assistant['id'], {'pid': process.pid})

    await assistant_menu(call, SelectAssistant(id=assistant['id']), state)


@dp.callback_query(F.data == 'assistant_settings')
async def assistant_settings(call: types.CallbackQuery, state: FSMContext):
    a_id = (await state.get_data())['assistant_id']

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='🗑 Удалить ассистента', callback_data='delete_assistant_confirm'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data=SelectAssistant(id=a_id).pack()))

    await call.message.edit_text('⚙️ Настройки', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'delete_assistant_confirm')
async def delete_assistant_confirm(call: types.CallbackQuery, state: FSMContext):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='Да, уверен', callback_data='delete_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='assistant_settings'))

    await call.message.edit_text(f'❗️ Вы уверены, что хотите удалить ассистента <b>{assistant["name"]}</b>?\n\n'
                                 f'Это действие нельзя будет отменить',
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'delete_assistant')
async def delete_assistant(call: types.CallbackQuery, state: FSMContext):
    await database.delete_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))

    await call.message.edit_text(f'✅ Ассистент удален', reply_markup=keyboard.as_markup())

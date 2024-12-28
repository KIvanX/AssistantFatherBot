import asyncio
import os
import signal

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.config import dp, bot
from core.filters import DeleteDocument, SelectAssistant
from core.states import EditAssistantStates, KnowledgeBaseAssistantStates, BaseAssistantStates
from core.utils import restart_working_assistant, start_assistant, init_personal_assistant


async def assistant_menu(data, callback_data: SelectAssistant, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data

    state_data = await state.get_data()
    await state.set_state(BaseAssistantStates.in_panel)
    assistant = await database.get_assistant(callback_data.id)
    change_status = 'Запустить бота' if assistant['status'] == 'stopped' else 'Остановить бота'

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=change_status, callback_data='change_assistant_status'))
    keyboard.row(types.InlineKeyboardButton(text='📚 База знаний', callback_data='knowledge_base'))
    keyboard.row(types.InlineKeyboardButton(text='✏️ Изменить', callback_data='edit_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⚙️ Настройки', callback_data='assistant_settings'))
    keyboard.row(types.InlineKeyboardButton(text='🏚 Меню', callback_data='start'))
    keyboard.adjust(1, 2, 1, 1)

    statuses = {'init': '🟡 Запускается...', 'working': '🟢 Работает', 'stopped': '🔴 Остановлен'}
    text = (f'Ассистент <b>{assistant["name"]}</b>\n\n'
            f'Ссылка на чат с ботом: @{assistant["username"]}\n\n'
            f'{statuses.get(assistant["status"], "?")}\n\n')

    if assistant['status'] == 'init':
        asyncio.create_task(wait_assistant_init(assistant['id'], state, (data, callback_data, state)))
    await state.update_data(assistant_id=callback_data.id)
    await bot.edit_message_text(text, chat_id=message.chat.id, reply_markup=keyboard.as_markup(),
                                message_id=state_data.get('message_id', message.message_id))


@dp.callback_query(F.data == 'edit_assistant')
async def edit_assistant(data, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await state.set_state(EditAssistantStates.edit)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='Имя', callback_data='name'))
    if not assistant['is_personal']:
        keyboard.add(types.InlineKeyboardButton(text='Start сообщение', callback_data='start_text'))
    keyboard.add(types.InlineKeyboardButton(text='Инструкция', callback_data='instruction'))
    keyboard.row(types.InlineKeyboardButton(text='Языковая модель', callback_data='assistant_model_type'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data=SelectAssistant(id=assistant['id']).pack()))

    text = (f'<b>Имя: </b>{assistant["name"]}\n\n'
            f'<b>Start сообщение: </b><code>{assistant["start_text"]}</code>\n\n'
            f'<b>Инструкция: </b>{assistant["instruction"] or "Не задана"}\n\n'
            f'<b>Языковая модель: </b>{assistant["model"]}\n\n'
            f'✏️ Выберите, что хотите изменить')
    if assistant['is_personal']:
        text = text.replace(f'<b>Start сообщение: </b><code>{assistant["start_text"]}</code>\n\n', '')
    message_id = (await state.get_data()).get('message_id', message.message_id)
    await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_id,
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['instruction', 'start_text', 'name']), EditAssistantStates.edit)
async def edit_assistant_parameter(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditAssistantStates.parameter)
    await state.update_data(parameter=call.data, message_id=call.message.message_id)
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    text = {'instruction': 'Инструкция: ' + assistant['instruction'] if assistant['instruction'] else '',
            'start_text': 'Start сообщение: <code>' + assistant['start_text'] + '</code>',
            'name': 'Имя ассистента: <code>' + assistant['name'] + '</code>'}[call.data]

    about = {'instruction': '<b>Инструкция</b> - это начальный промпт, которому будет следовать '
                            'ассистент при общении с клиентами. \nНапример: Ты - официант Николай, '
                            'работаешь в ресторане "Гастрономия". Помогай клиентам сделать заказ.',
             'start_text': '<b>Start сообщение</b> - это сообщение, которое ассистент отправит клиенту '
                           'при команде /start',
             'name': '<b>Имя ассистента</b> - это название, которое будет отображаться в меню.'}[call.data]
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='edit_assistant'))

    await call.message.edit_text(text + '\n\n' + about + f'\n\n✏️ Введите новое значение',
                                 reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', EditAssistantStates.parameter)
async def edit_assistant_commit(message: types.Message, state: FSMContext):
    await state.set_state()

    state_data = await state.get_data()
    await database.update_assistant(state_data['assistant_id'], {state_data['parameter']: message.text})

    await restart_working_assistant(state_data['assistant_id'])
    await message.delete()
    await edit_assistant(message, state)


@dp.callback_query(F.data == 'knowledge_base')
async def knowledge_base(data, state: FSMContext):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    state_data = await state.get_data()
    await state.set_state()
    a_id = state_data['assistant_id']

    text = '📚 Загруженные документы\n\n'
    for doc in (await database.get_documents(a_id)):
        text += '├ <b>' + doc['file_name'] + '</b>\n'
    text = text[:text.rfind('├')] + '└' + text[text.rfind('├') + 1:] if '├' in text else text + 'Пусто'

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='➕ Добавить документ', callback_data='add_document'))
    if not text.endswith('Пусто'):
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
    await call.message.edit_text('📚 Отправьте нужный документ\n\n'
                                 'Поддерживаются следующие расширения: doc, docx, txt, pdf, html, json, py и другие '
                                 'форматы типы, которые широко используются для хранения текстовой информации.',
                                 reply_markup=keyboard.as_markup())


@dp.message(F.document, KnowledgeBaseAssistantStates.add)
async def add_document_commit(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    assistant = await database.get_assistant(state_data['assistant_id'])

    path = f'core/assistant/internal_core/static/{state_data["assistant_id"]}/documents'
    if not os.path.exists(path):
        os.makedirs(path)

    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, path + '/' + message.document.file_name)
    await database.add_document(assistant['id'], message.document.file_name)

    await restart_working_assistant(state_data['assistant_id'])
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
    if os.path.isfile('core/assistant/internal_core/static/' + str(doc['assistant_id']) + '/documents/' +
                      doc['file_name']):
        os.remove('core/assistant/internal_core/static/' + str(doc['assistant_id']) + '/documents/' + doc['file_name'])

    await restart_working_assistant(doc['assistant_id'])
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
        await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})
    else:
        if not assistant['is_personal']:
            await start_assistant(assistant['id'])
        else:
            if assistant['status'] == 'stopped':
                for a in await database.get_assistants(call.message.chat.id):
                    if a['is_personal'] and a['status'] != 'stopped':
                        await database.update_assistant(a['id'], {'status': 'stopped'})
                asyncio.create_task(init_personal_assistant(assistant))
            else:
                await database.update_assistant(assistant['id'], {'status': 'stopped'})

    await assistant_menu(call, SelectAssistant(id=assistant['id']), state)


@dp.callback_query(F.data == 'assistant_model_type')
async def assistant_model(call: types.CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='Opensource (Gemma, Llama)', callback_data='opensource_models'))
    keyboard.row(types.InlineKeyboardButton(text='Коммерческие (OpenAI, GigaChat)', callback_data='commercial_models'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='edit_assistant'))

    await call.message.edit_text('Выберите тип языковой модели', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'opensource_models')
async def opensource_models(call: types.CallbackQuery, state: FSMContext):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    for model in ['gemma2-9b-it', 'gemma-7b-it', 'llama-3.1-70b-versatile', 'llama-3.1-70b-specdec',
                  'llama-3.1-8b-instant', 'llama-3.2-1b-preview', 'llama-3.2-3b-preview', 'llama3-70b-8192',
                  'llama3-8b-8192', 'mixtral-8x7b-32768']:
        modes_txt = '✅ ' + model if model == assistant['model'] else model
        keyboard.add(types.InlineKeyboardButton(text=modes_txt, callback_data=f'assistant_model_{model}'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='assistant_model_type'))

    await call.message.edit_text('Выберите языковую модель ассистента', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'commercial_models')
async def commercial_models(call: types.CallbackQuery, state: FSMContext):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    for model in ["gpt-4o", "chatgpt-4o-latest", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
                  "GigaChat", "GigaChat-Pro", "GigaChat-Max"]:
        modes_txt = '✅ ' + model if model == assistant['model'] else model
        keyboard.add(types.InlineKeyboardButton(text=modes_txt, callback_data=f'assistant_model_{model}'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='assistant_model_type'))

    await call.message.edit_text('Выберите языковую модель ассистента', reply_markup=keyboard.as_markup())


@dp.callback_query(lambda call: call.data.startswith('assistant_model_'))
async def assistant_models_commit(call: types.CallbackQuery, state: FSMContext):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await database.update_assistant(assistant['id'], {'model': call.data[16:]})
    await call.answer(f'Выбрана модель {call.data[16:]}')
    await restart_working_assistant(assistant['id'])
    if 'gpt' in call.data.lower() or 'gigachat' in call.data.lower():
        await commercial_models(call, state)
    else:
        await opensource_models(call, state)


async def wait_assistant_init(assistant_id, state: FSMContext, params):
    assistant = await database.get_assistant(assistant_id)
    while assistant['status'] == 'init':
        await asyncio.sleep(2)
        assistant = await database.get_assistant(assistant_id)
    try:
        if await state.get_state() == BaseAssistantStates.in_panel:
            await assistant_menu(*params)
    except:
        pass

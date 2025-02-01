import asyncio
import os
import signal
import textract

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core import database
from core.assistant.internal_core.utils import price
from core.config import dp, bot
from core.filters import DeleteDocument, SelectAssistant
from core.states import EditAssistantStates, KnowledgeBaseAssistantStates, BaseAssistantStates
from core.utils import restart_working_assistant, start_assistant, init_personal_assistant, paid_model


async def assistant_menu(data, callback_data: SelectAssistant, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data

    state_data = await state.get_data()
    await state.set_state(BaseAssistantStates.in_panel)
    assistant = await database.get_assistant(callback_data.id)
    change_status = await T('Запустить бота') if assistant['status'] == 'stopped' else await T('Остановить бота')

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=change_status, callback_data='change_assistant_status'))
    keyboard.row(types.InlineKeyboardButton(text='📚 ' + await T('База знаний'), callback_data='knowledge_base'))
    keyboard.row(types.InlineKeyboardButton(text='✏️ ' + await T('Изменить'), callback_data='edit_assistant'))
    keyboard.row(types.InlineKeyboardButton(text='⚙️ ' + await T('Настройки'), callback_data='assistant_settings'))
    keyboard.row(types.InlineKeyboardButton(text='🏚 ' + await T('Меню'), callback_data='start'))
    keyboard.adjust(1, 2, 1, 1)

    statuses = {'init': '🟡 ' + await T('Запускается...'), 'working': '🟢 ' + await T('Работает'),
                'stopped': '🔴 ' + await T('Остановлен')}
    if not assistant['is_personal']:
        text = await T(f'Ассистент <b>_1</b>\n\n'
                       f'Ссылка на чат с ботом: @_2\n\n'
                       f'Языковая модель: _3\n\n'
                       f'_4', assistant["name"], assistant["username"], assistant["model"],
                       statuses.get(assistant["status"], "?"))
    else:
        text = await T(f'Личный ассистент <b>_1</b>\n\n'
                       f'Языковая модель: _2\n\n_3', assistant["name"], assistant["model"],
                       statuses.get(assistant["status"], "?"))

    if assistant['status'] == 'init':
        asyncio.create_task(wait_assistant_init(assistant['id'], state, (data, callback_data, state, T)))
    await state.update_data(assistant_id=callback_data.id)
    try:
        await bot.edit_message_text(text, chat_id=message.chat.id, reply_markup=keyboard.as_markup(),
                                    message_id=state_data.get('message_id', message.message_id))
    except:
        pass


@dp.callback_query(F.data == 'edit_assistant')
async def edit_assistant(data, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await state.set_state(EditAssistantStates.edit)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text=await T('Имя'), callback_data='name'))
    if not assistant['is_personal']:
        keyboard.add(types.InlineKeyboardButton(text=await T('Start сообщение'), callback_data='start_text'))
    keyboard.add(types.InlineKeyboardButton(text=await T('Инструкция'), callback_data='instruction'))
    keyboard.row(types.InlineKeyboardButton(text=await T('Языковая модель'), callback_data='assistant_model_type'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'),
                                            callback_data=SelectAssistant(id=assistant['id']).pack()))

    text = await T(f'<b>Имя: </b>_1\n\n'
                   f'<b>Start сообщение: </b><code>_2</code>\n\n'
                   f'<b>Инструкция: </b>_3\n\n'
                   f'<b>Языковая модель: </b>_4\n\n'
                   f'_5 Выберите, что хотите изменить', assistant["name"],
                   assistant["start_text"], assistant["instruction"] or "Не задана", assistant["model"], '✏️')
    if assistant['is_personal']:
        text = text.replace(f'<b>Start сообщение: </b><code>{assistant["start_text"]}</code>\n\n', '')
    message_id = (await state.get_data()).get('message_id', message.message_id)
    await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_id,
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['instruction', 'start_text', 'name']), EditAssistantStates.edit)
async def edit_assistant_parameter(call: types.CallbackQuery, state: FSMContext, T):
    await state.set_state(EditAssistantStates.parameter)
    await state.update_data(parameter=call.data, message_id=call.message.message_id)
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    text = {'instruction': await T('Инструкция') + ': ' + assistant['instruction'] if assistant['instruction'] else '',
            'start_text': await T('Start сообщение') + ': <code>' + assistant['start_text'] + '</code>',
            'name': await T('Имя ассистента') + ': <code>' + assistant['name'] + '</code>'}[call.data]

    about = {'instruction': await T('<b>Инструкция</b> - это начальный промпт, которому будет следовать '
                                    'ассистент при общении с клиентами. \nНапример: Ты - официант Николай, '
                                    'работаешь в ресторане "Гастрономия". Помогай клиентам сделать заказ.'),
             'start_text': await T('<b>Start сообщение</b> - это сообщение, которое ассистент отправит клиенту '
                                   'при команде /start'),
             'name': await T('<b>Имя ассистента</b> - это название, которое будет отображаться в меню.')}[call.data]
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='edit_assistant'))

    await call.message.edit_text(text + '\n\n' + about + f'\n\n✏️ ' + await T('Введите новое значение'),
                                 reply_markup=keyboard.as_markup())


@dp.message(F.text[0] != '/', EditAssistantStates.parameter)
async def edit_assistant_commit(message: types.Message, state: FSMContext, T):
    await state.set_state()

    state_data = await state.get_data()
    await database.update_assistant(state_data['assistant_id'], {state_data['parameter']: message.text})

    await restart_working_assistant(state_data['assistant_id'])
    await message.delete()
    await edit_assistant(message, state, T)


@dp.callback_query(F.data == 'knowledge_base')
async def knowledge_base(data, state: FSMContext, T):
    message: types.Message = data.message if isinstance(data, types.CallbackQuery) else data
    state_data = await state.get_data()
    await state.set_state()
    a_id = state_data['assistant_id']

    text = '📚 ' + await T('Загруженные документы') + '\n\n'
    for doc in (await database.get_documents(a_id)):
        text += '├ <b>' + doc['file_name'].split('.')[0] + '</b>\n'
    text = text[:text.rfind('├')] + '└' + text[text.rfind('├') + 1:] if '├' in text else text + await T('Пусто')

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='➕ ' + await T('Добавить документ'), callback_data='add_document'))
    if not text.endswith('Пусто'):
        keyboard.row(types.InlineKeyboardButton(text='➖ ' + await T('Удаление документов'),
                                                callback_data='delete_documents'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'),
                                            callback_data=SelectAssistant(id=a_id).pack()))

    await bot.edit_message_text(text, chat_id=message.chat.id,
                                message_id=state_data.get('message_id', message.message_id),
                                reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'add_document')
async def add_document(call: types.CallbackQuery, state: FSMContext, T):
    await state.set_state(KnowledgeBaseAssistantStates.add)
    await state.update_data(message_id=call.message.message_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='knowledge_base'))
    await call.message.edit_text('📚 ' + await T('Отправьте нужный документ\n\n'
                                                'Поддерживаются следующие расширения: doc, docx, txt, pdf, '
                                                'html, json, py и другие форматы типы, '
                                                'которые широко используются для хранения текстовой информации.'),
                                 reply_markup=keyboard.as_markup())


@dp.message(F.document, KnowledgeBaseAssistantStates.add)
async def add_document_commit(message: types.Message, state: FSMContext, T):
    state_data = await state.get_data()
    assistant = await database.get_assistant(state_data['assistant_id'])
    mes = await message.answer('📚 ' + await T('Обработка документа...'))

    path = f'core/assistant/internal_core/static/{state_data["assistant_id"]}/documents'
    if not os.path.exists(path):
        os.makedirs(path)

    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, path + '/' + message.document.file_name)

    new_name = message.document.file_name.replace('.', '_') + '.txt'
    text = textract.process(path + '/' + message.document.file_name).decode('utf-8')
    with open(path + '/' + new_name, 'w') as f:
        f.write(text)
    os.remove(path + '/' + message.document.file_name)

    await mes.delete()
    await database.add_document(assistant['id'], new_name)
    await restart_working_assistant(state_data['assistant_id'])
    await message.delete()
    await knowledge_base(message, state, T)


@dp.callback_query(F.data == 'delete_documents')
async def delete_documents(call: types.CallbackQuery, state: FSMContext, T):
    a_id = (await state.get_data())['assistant_id']

    keyboard = InlineKeyboardBuilder()
    for doc in (await database.get_documents(a_id)):
        keyboard.add(types.InlineKeyboardButton(text=doc['file_name'],
                                                callback_data=DeleteDocument(id=doc['id']).pack()))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='knowledge_base'))

    await call.message.edit_text(await T('Выберите документ, который нужно удалить'), reply_markup=keyboard.as_markup())


@dp.callback_query(DeleteDocument.filter())
async def delete_documents_commit(call: types.CallbackQuery, state: FSMContext, callback_data: DeleteDocument, T):
    await state.set_state(KnowledgeBaseAssistantStates.add)
    await state.update_data(message_id=call.message.message_id)

    doc = await database.get_document(callback_data.id)
    await database.delete_document(doc['id'])
    if os.path.isfile('core/assistant/internal_core/static/' + str(doc['assistant_id']) + '/documents/' +
                      doc['file_name']):
        os.remove('core/assistant/internal_core/static/' + str(doc['assistant_id']) + '/documents/' + doc['file_name'])

    await restart_working_assistant(doc['assistant_id'])
    await call.answer('✅ ' + await T('Документ удален'))
    await delete_documents(call, state, T)


@dp.callback_query(F.data == 'change_assistant_status')
async def change_assistant_status(call: types.CallbackQuery, state: FSMContext, T):
    user = await database.get_users(call.message.chat.id)
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    if user['balance'] <= 0 and paid_model(assistant['model'].lower()):
        await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})
        return await call.answer(await T('На вашем балансе недостаточно средств для работы этого ассистента'))

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
                await database.update_assistant(assistant['id'], {'status': 'init'})
                asyncio.create_task(init_personal_assistant(assistant))
            else:
                await database.update_assistant(assistant['id'], {'status': 'stopped'})

    await assistant_menu(call, SelectAssistant(id=assistant['id']), state, T)


@dp.callback_query(F.data == 'assistant_model_type')
async def assistant_model(call: types.CallbackQuery, T):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text=await T('Opensource (Gemma, Llama)'),
                                            callback_data='opensource_models'))
    keyboard.row(types.InlineKeyboardButton(text=await T('Коммерческие (OpenAI, GigaChat, Claude)'),
                                            callback_data='commercial_models'))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='edit_assistant'))

    await call.message.edit_text(await T('Выберите тип языковой модели'), reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'opensource_models')
async def opensource_models(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    for model in ['gemma2-9b-it', 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant',
                  'llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768']:
        modes_txt = '✅ ' + model if model == assistant['model'] else model
        keyboard.add(types.InlineKeyboardButton(text=modes_txt, callback_data=f'assistant_model_{model}'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='assistant_model_type'))

    await call.message.edit_text(await T('Выберите языковую модель ассистента\n\n'
                                         '❕ Все Opensource модели бесплатные'), reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'commercial_models')
async def commercial_models(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])

    keyboard = InlineKeyboardBuilder()
    for model in ["gpt-4o", "gpt-4o-2024-11-20", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
                  "GigaChat", "GigaChat-Pro", "GigaChat-Max", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest",
                  "claude-3-opus-latest"]:
        modes_txt = ('✅ ' + model if model == assistant['model'] else model) + ' - '
        pr = price[model]
        if 'gpt' in model.lower() or 'claude' in model.lower():
            modes_txt += str(round((pr['input_cost'] / 10000 * 800 + pr['input_cost'] / 10000 * 200), 2)) + '₽'
        elif 'gigachat' in model.lower():
            modes_txt += str(round(pr['output_cost'] / 5000000 * 1000, 2)) + '₽'

        keyboard.add(types.InlineKeyboardButton(text=modes_txt, callback_data=f'assistant_model_{model}'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ Назад', callback_data='assistant_model_type'))

    await call.message.edit_text(await T('Выберите языковую модель ассистента\n\n'
                                         '❕ Цена отражает среднюю стоимость одного запроса'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(lambda call: call.data.startswith('assistant_model_'))
async def assistant_models_commit(call: types.CallbackQuery, state: FSMContext, T):
    assistant = await database.get_assistant((await state.get_data())['assistant_id'])
    await database.update_assistant(assistant['id'], {'model': call.data[16:]})
    if 'gpt' not in call.data.lower() or call.data[16:] == 'gpt-4':
        await database.update_assistant(assistant['id'], {'own_search': True})

    if assistant['model'] == call.data[16:]:
        return await call.answer()

    await call.answer(await T('Выбрана модель') + ' ' + call.data[16:])
    await restart_working_assistant(assistant['id'])
    if paid_model(call.data):
        await commercial_models(call, state, T)
    else:
        await opensource_models(call, state, T)


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

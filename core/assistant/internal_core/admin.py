import os

from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.assistant.internal_core import database
from core.assistant.internal_core.config import dp
from telegraph import Telegraph


@dp.callback_query(F.data == 'admin')
async def admin_menu(data, state: FSMContext, T):
    message = data.message if isinstance(data, types.CallbackQuery) else data
    user = next((u for u in await database.get_assistant_users(dp.assistant['id']) if u['user_id'] == message.chat.id))
    await state.clear()
    if message.chat.id != dp.assistant['user_id'] and not user['is_admin']:
        return 0

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='📈 ' + await T('Статистика'), callback_data='statistic'))
    keyboard.row(types.InlineKeyboardButton(text='💬 ' + await T('Диалоги'), callback_data='dialogs'))
    keyboard.row(types.InlineKeyboardButton(text='📣 ' + await T('Рассылка'), callback_data='mailing'))
    keyboard.row(types.InlineKeyboardButton(text='🧑‍💻 ' + await T('Администраторы'), callback_data='update_admins'))

    text = '💼 ' + await T('Меню администратора ассистента') + f' <b>{dp.assistant["name"]}</b>'
    if isinstance(data, types.CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard.as_markup())
    else:
        await message.answer(text, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == 'statistic')
async def statistic(call: types.CallbackQuery, T):
    info = await database.get_statistics(dp.assistant['id'])
    info['del_users'] = info['users'] - info['alive_users']

    text = await T(f'<u><i>Статистика</i></u>\n\n'
                   f'Всего _1: _2\n'
                   f'Живых _1: _3 (_4%)\n'
                   f'Удалённых _1: _5 (_6%)\n\n'
                   f'Новых _1 за час: +_7 (+_8%)\n'
                   f'Новых _1 за день: +_9 (+_10%)\n'
                   f'Новых _1 за месяц: +_11 (+_12%)\n\n'
                   f'Новых _13 за час: +_14 (+_15%)\n'
                   f'Новых _13 за день: +_16 (+_17%)\n'
                   f'Новых _13 за месяц: +_18 (+_19%)\n\n',
                   '🙋', info["users"], info["alive_users"], round(info["alive_users"] / info["users"] * 100, 2),
                   info["del_users"], round(info["del_users"] / info["users"] * 100, 2),
                   info["new_per_hour"], round(info["new_per_hour"] / info["users"] * 100, 2),
                   info["new_per_day"], round(info["new_per_day"] / info["users"] * 100, 2),
                   info["new_per_month"], round(info["new_per_month"] / info["users"] * 100, 2), '📨',
                   info["new_mes_hour"], round(info["new_mes_hour"] / info["messages"] * 100, 2),
                   info["new_mes_day"], round(info["new_mes_day"] / info["messages"] * 100, 2),
                   info["new_mes_month"], round(info["new_mes_month"] / info["messages"] * 100, 2))

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='admin'))
    await call.message.edit_text(text, reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['dialogs_page_left', 'dialogs_page_right']))
@dp.callback_query(F.data == 'dialogs')
async def users_dialog(call: types.CallbackQuery, state: FSMContext, T):
    users = await database.get_assistant_users(dp.assistant['id'])

    page = (await state.get_data()).get('page', 0)
    if call.data in ['dialogs_page_left', 'dialogs_page_right']:
        page = page + 1 if call.data == 'dialogs_page_right' else page - 1
        await state.update_data(page=page)

    keyboard = InlineKeyboardBuilder()
    for user in users[page * 10: (page + 1) * 10]:
        keyboard.add(types.InlineKeyboardButton(text=f'{user["name"]}', callback_data=f'dialog_{user["user_id"]}'))
    if page > 0:
        keyboard.add(types.InlineKeyboardButton(text='<', callback_data='dialogs_page_left'))
    if page < len(users) // 10:
        keyboard.add(types.InlineKeyboardButton(text='>', callback_data='dialogs_page_right'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='admin'))

    num_pages = len(users) // 10 + (1 if len(users) % 10 else 0)
    await call.message.edit_text(f'💬 ' + await T('<b>Диалоги</b> стр. _1\n\n'
                                                 f'Выберите пользователя', f'{page + 1}/{num_pages}'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.startswith('dialog_'))
async def dialog(call: types.CallbackQuery, T):
    await call.message.edit_text(await T('Загрузка диалога...'))

    user_id = int(call.data.split('_')[1])
    messages = await database.get_messages(user_id, dp.assistant['id'])
    user = next((user for user in await database.get_assistant_users(dp.assistant['id']) if user['user_id'] == user_id))

    text = ''
    for message in messages:
        text += f'<b>{message["author"]}</b>: {message["message"]}<br>'

    telegraph = Telegraph(os.environ["TELEGRAPH_API_KEY"])
    response = telegraph.create_page(f'💬 ' + await T('Диалог с пользователем') + f' {user["name"]}', html_content=text)

    keyboard = InlineKeyboardBuilder()
    keyboard.row(types.InlineKeyboardButton(text='💬 ' + await T('Посмотреть диалог'), url=response['url']))
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='dialogs'))
    await call.message.edit_text('✅ ' + await T('Статься с диалогом создана'), reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.in_(['admins_page_left', 'admins_page_right']))
@dp.callback_query(F.data == 'update_admins')
async def update_admins(call: types.CallbackQuery, state: FSMContext, T):
    users = [u for u in await database.get_assistant_users(dp.assistant['id']) if u['user_id'] != call.message.chat.id]

    page = (await state.get_data()).get('page', 0)
    if call.data in ['admins_page_left', 'admins_page_right']:
        page = page + 1 if call.data == 'admins_page_right' else page - 1
        await state.update_data(page=page)

    keyboard = InlineKeyboardBuilder()
    for user in users[page * 10: (page + 1) * 10]:
        user['name'] = '✅ ' + user['name'] if user['is_admin'] else user['name']
        keyboard.add(types.InlineKeyboardButton(text=f'{user["name"]}', callback_data=f'admins_{user["user_id"]}'))
    if page > 0:
        keyboard.add(types.InlineKeyboardButton(text='<', callback_data='admins_page_left'))
    if page < len(users) // 10:
        keyboard.add(types.InlineKeyboardButton(text='>', callback_data='admins_page_right'))
    keyboard.adjust(2)
    keyboard.row(types.InlineKeyboardButton(text='⬅️ ' + await T('Назад'), callback_data='admin'))

    num_pages = len(users) // 10 + (1 if len(users) % 10 else 0)
    await call.message.edit_text(f'🧑‍💻 ' + await T('<b>Администраторы</b> стр. _1\n\n'
                                                   'Выберите пользователя', f'{page + 1}/{num_pages}'),
                                 reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.startswith('admins_'))
async def commit_update_admin(call: types.CallbackQuery, state: FSMContext, T):
    user_id = int(call.data.split('_')[1])
    user = next((user for user in await database.get_assistant_users(dp.assistant['id']) if user['user_id'] == user_id))
    await database.update_assistant_user(user_id, {'is_admin': not user['is_admin']})
    await call.answer(await T('Статус администратора обновлен'))
    await update_admins(call, state, T)

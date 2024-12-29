import asyncio

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.enums.chat_action import ChatAction
from . import database as in_database
from .config import dp as in_dp
from .utils import calc_price


async def init_openai_assistant(external_data=None):
    database = external_data['database'] if external_data else in_database
    assistant = external_data['assistant'] if external_data else in_dp.assistant
    client = external_data['client'] if external_data else in_dp.client

    vector_store = await client.beta.vector_stores.create(name="Documents")
    for doc in await database.get_documents(assistant['id']):
        with open(f'core/assistant/internal_core/static/{assistant["id"]}/documents/' + doc['file_name'], 'rb') as f:
            await client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=[(doc['file_name'], f)])

    assistant = await client.beta.assistants.create(
        name="Assistant",
        instructions=assistant["instruction"],
        model=assistant['model'],
        tools=[{"type": "file_search"}],
        tool_resources={
            "file_search": {"vector_store_ids": [vector_store.id]}
        },
    )

    return assistant.id


async def get_openai_message(message: types.Message, state: FSMContext, external_data=None):
    bot = external_data['bot'] if external_data else in_dp.bot
    database = external_data['database'] if external_data else in_database
    assistant_id = external_data['assistant_id'] if external_data else in_dp.assistant
    client = external_data['client'] if external_data else in_dp.client

    status = ['wait']
    asyncio.create_task(typing(bot, message, status))

    if 'thread_id' not in (await state.get_data()):
        thread = await client.beta.threads.create()
        await state.update_data(thread_id=thread.id)

    await client.beta.threads.messages.create(
        thread_id=(await state.get_data()).get('thread_id'),
        content=message.text,
        role="user"
    )

    run = await client.beta.threads.runs.create_and_poll(
        thread_id=(await state.get_data()).get('thread_id'),
        assistant_id=assistant_id,
    )

    status[0] = 'completed'
    if run.status == "completed":
        messages = await client.beta.threads.messages.list(
            thread_id=(await state.get_data()).get('thread_id'),
            run_id=run.id
        )

        for mes in list(messages)[0][1][::-1]:
            if mes.role == "assistant":
                for block in mes.content:
                    if block.type == "text":
                        text = block.text.value
                        while '【' in text and '】' in text:
                            text = text[:text.find('【')] + text[text.find('】') + 1:]
                        price = await calc_price({'model_name': run.model,
                                                  'token_usage': {'prompt_tokens': run.usage.prompt_tokens,
                                                                  'completion_tokens': run.usage.completion_tokens}})
                        user = await database.get_users(message.chat.id)
                        await database.update_user(message.chat.id, {'balance': user['balance'] - price})
                        text += f'\n<i>Цена: {round(price, 8)}₽</i>'
                        await message.answer(text)
    else:
        await message.answer('Что-то пошло не так')


async def typing(bot, message: types.Message, status: list):
    while status[0] == 'wait':
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(8)

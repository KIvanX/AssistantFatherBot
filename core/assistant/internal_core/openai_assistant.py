import asyncio

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.enums.chat_action import ChatAction
from internal_core import database
from internal_core.config import dp


async def init_openai_assistant():
    vector_store = await dp.client.beta.vector_stores.create(name="Documents")
    for doc in await database.get_documents(dp.assistant['id']):
        with open(f'core/assistant/internal_core/static/{dp.assistant["id"]}/documents/' + doc['file_name'], 'rb') as f:
            await dp.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=[(doc['file_name'], f)])

    assistant = await dp.client.beta.assistants.create(
        name="Assistant",
        instructions=dp.assistant["instruction"],
        model='gpt-4o-mini',
        tools=[{"type": "file_search"}],
        tool_resources={
            "file_search": {"vector_store_ids": [vector_store.id]}
        },
    )

    dp.assistant_id = assistant.id


async def get_openai_message(message: types.Message, state: FSMContext):
    status = ['wait']
    asyncio.create_task(typing(message, status))

    if 'thread_id' not in (await state.get_data()):
        thread = await dp.client.beta.threads.create()
        await state.update_data(thread_id=thread.id)

    await dp.client.beta.threads.messages.create(
        thread_id=(await state.get_data()).get('thread_id'),
        content=message.text,
        role="user"
    )

    run = await dp.client.beta.threads.runs.create_and_poll(
        thread_id=(await state.get_data()).get('thread_id'),
        assistant_id=dp.assistant_id,
    )

    status[0] = 'completed'
    if run.status == "completed":
        messages = await dp.client.beta.threads.messages.list(
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
                        await message.answer(text)
    else:
        await message.answer('Что-то пошло не так')


async def typing(message: types.Message, status: list):
    while status[0] == 'wait':
        await dp.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(8)

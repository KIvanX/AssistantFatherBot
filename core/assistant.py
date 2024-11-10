
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile

from core.config import dp, bot, client


class AssistantStates(StatesGroup):
    fileSearchWorkState = State()
    codeInterpreterWorkState = State()


@dp.message(Command('file_search'))
async def file_search_assistant(message: types.Message, state: FSMContext):
    if 'assistant_id' in await state.get_data():
        await state.clear()
        return message.answer('Ассистент сброшен.')

    return await message.answer(f'file_search Ассистент может отвечать на вопросы, '
                                f'используя информацию из документа.\n\n'
                                f'Для создания Ассистента отправь файл с расширением txt, docx или pdf. '
                                f'К файлу добавь инструкцию.\n\nНапример: '
                                f'<code>file_search: Ты - официант. Помоги клиентам сделать заказ.</code>')


@dp.message(F.document, F.caption.startswith('file_search:'))
async def create_file_search_assistant(message: types.Message, state: FSMContext):
    mes = await message.answer('Принято. Инициализация...')
    file_info = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    vector_store = client.beta.vector_stores.create(name="Documents")

    try:
        await mes.edit_text('Загрузка документа...')
        client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=[(message.document.file_name, downloaded_file)])
    except:
        return await mes.edit_text('Не удалось загрузить документ. Возможно, расширение не поддерживается')

    await mes.edit_text('Создание ассистента...')
    assistant = client.beta.assistants.create(
        name="Assistant",
        instructions=message.text[13:],
        model='gpt-4o-mini',
        tools=[{"type": "file_search"}],
        tool_resources={
            "file_search": {"vector_store_ids": [vector_store.id]}
        },
    )

    await mes.edit_text('Создание потока...')
    thread = client.beta.threads.create()

    await state.update_data(thread_id=thread.id, assistant_id=assistant.id)
    await state.set_state(AssistantStates.fileSearchWorkState)
    await mes.edit_text(f'Все готово, можешь отправлять запросы Ассистенту.\n\n'
                        f'Чтобы закончить диалог с Ассистентом, отправь команду /file_search.')


@dp.message(F.text[0] != '/', AssistantStates.fileSearchWorkState)
async def get_text_file_search(message: types.Message, state: FSMContext):
    mes = await message.answer('Запрос получен, пожалуйста, подождите...')
    client.beta.threads.messages.create(
        thread_id=(await state.get_data()).get('thread_id'),
        content=message.text,
        role="user"
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=(await state.get_data()).get('thread_id'),
        assistant_id=(await state.get_data()).get('assistant_id'),
    )
    await mes.delete()

    answers = []
    if run.status == "completed":
        messages = client.beta.threads.messages.list(
            thread_id=(await state.get_data()).get('thread_id'),
            run_id=run.id
        )
        for mes in messages:
            if mes.role == "assistant":
                for block in mes.content:
                    if block.type == "text":
                        answers.append(block.text.value)

    for text in answers or ['Что-то пошло не так']:
        await message.answer(text)


@dp.message(Command('code_interpreter'))
async def code_interpreter_assistant(message: types.Message, state: FSMContext):
    if 'assistant_id' in await state.get_data():
        await state.clear()
        return message.answer('Ассистент сброшен.')

    return await message.answer(f'code_interpreter Ассистент может анализировать документы, генерируя и запуская код, '
                                f'для решения поставленной задачи.\n\n'
                                f'Для создания Ассистента отправь файл с расширением csv. '
                                f'К файлу добавь инструкцию.\n\nНапример: '
                                f'<code>code_interpreter: Ты - дата-аналитик. '
                                f'Отвечай на вопросы по прикрепленному csv файлу.</code>')


@dp.message(F.document, F.caption.startswith('code_interpreter:'))
async def create_code_interpreter_assistant(message: types.Message, state: FSMContext):
    mes = await message.answer('Принято. Инициализация...')
    file_info = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    try:
        await mes.edit_text('Загрузка документа...')
        file = client.files.create(
            file=(message.document.file_name, downloaded_file),
            purpose='assistants')
    except:
        return await mes.edit_text('Не удалось загрузить документ. Возможно, расширение не поддерживается')

    await mes.edit_text('Создание ассистента...')
    assistant = client.beta.assistants.create(
        instructions=message.text[18:],
        model="gpt-4o",
        tools=[{"type": "code_interpreter"}],
        tool_resources={
            "code_interpreter": {
                "file_ids": [file.id]
            }
        }
    )

    await mes.edit_text('Создание потока...')
    thread = client.beta.threads.create()

    await state.update_data(thread_id=thread.id, assistant_id=assistant.id)
    await state.set_state(AssistantStates.codeInterpreterWorkState)
    await mes.edit_text(f'Все готово, можешь отправлять запросы Ассистенту.\n\n'
                        f'Чтобы закончить диалог с Ассистентом, отправь команду /code_interpreter.')


@dp.message(F.text[0] != '/', AssistantStates.codeInterpreterWorkState)
async def get_text_code_interpreter(message: types.Message, state: FSMContext):
    mes = await message.answer('Запрос получен, пожалуйста, подождите...')
    client.beta.threads.messages.create(
        thread_id=(await state.get_data()).get('thread_id'),
        content=message.text,
        role="user"
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=(await state.get_data()).get('thread_id'),
        assistant_id=(await state.get_data()).get('assistant_id'),
    )
    await mes.delete()

    if run.status != "completed":
        with open('core/static/error.json', 'w') as f:
            f.write(run.model_dump_json(indent=4))
        return await message.answer('К сожалению, ошибка: ' + run.last_error.message)

    answers = []
    messages = client.beta.threads.messages.list(
        thread_id=(await state.get_data()).get('thread_id'),
        run_id=run.id
    )
    for mes in messages:
        if mes.role == "assistant":
            for block in mes.content:
                if block.type == "text":
                    answers.append({'type': 'text',
                                    'text': block.text.value})
                    if block.text.annotations:
                        for annotation in block.text.annotations:
                            if annotation.type == "file_path":
                                answers.append({"type": "file",
                                                "filename": annotation.text.split('/')[-1],
                                                "file": annotation.file_path.file_id})
                elif block.type == "image_file":
                    answers.append({"type": "image",
                                    "file": block.image_file.file_id})

    with open('core/static/answer.json', 'w') as f:
        f.write(messages.model_dump_json(indent=4))

    for ans in answers[::-1]:
        if ans['type'] == 'text':
            await message.answer(ans['text'])
        elif ans['type'] == 'image':
            with open(f"core/static/image.png", "wb") as f:
                f.write(client.files.content(ans['file']).read())
            await message.answer_photo(FSInputFile("core/static/image.png"))
        elif ans['type'] == 'file':
            with open(f"core/static/{ans['filename']}", "wb") as f:
                f.write(client.files.content(ans['file']).read())
            await message.answer_document(FSInputFile(f"core/static/{ans['filename']}"))

    run_steps = client.beta.threads.runs.steps.list(
        thread_id=(await state.get_data()).get('thread_id'),
        run_id=run.id
    )

    codes = ''
    for step in run_steps.data:
        if step.step_details.type == 'tool_calls':
            for tool_call in step.step_details.tool_calls:
                codes += tool_call.code_interpreter.input + '\n\n'
    if codes:
        await message.answer(f'Используемый для анализа код:\n\n```python\n{codes}```', parse_mode='MarkdownV2')

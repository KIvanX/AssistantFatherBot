
import os
from aiogram import types
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from chromadb.config import Settings
from langchain_community.chat_models import GigaChat
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import database as in_database
from .custom_models import JinaEmbeddings, ChatEdenAI
from .config import dp as in_dp
from .utils import calc_price, check_balance


async def init_assistant(external_data=None):
    database = external_data['database'] if external_data else in_database
    assistant = external_data['assistant'] if external_data else in_dp.assistant

    if 'gigachat' in assistant["model"].lower():
        chat_model = GigaChat(credentials=os.environ['GIGACHAT_API_KEY'], model=assistant["model"],
                              verify_ssl_certs=False)
    elif 'gpt' in assistant["model"].lower():
        chat_model = ChatOpenAI(api_key=os.environ['OPENAI_API_KEY'], model=assistant["model"])
    elif 'claude' in assistant["model"].lower():
        chat_model = ChatEdenAI(api_key=os.environ["EDENAI_API_KEY"], provider="anthropic", model=assistant["model"])
    else:
        chat_model = ChatGroq(temperature=0.6, model_name=assistant["model"], api_key=os.environ['GROQ_API_KEY'])

    documents, vector_db = [], None
    for doc in await database.get_documents(assistant['id']):
        path = f'core/assistant/internal_core/static/{assistant["id"]}/documents/' + doc['file_name']
        documents.extend(TextLoader(path).load())

    if documents:
        if 'jina' in assistant['emb_model']:
            embedding_model = JinaEmbeddings(os.environ['JINA_API_KEY'], assistant['emb_model'])
        else:
            embedding_model = OpenAIEmbeddings(openai_api_key=os.environ['OPENAI_API_KEY'],
                                               model=assistant['emb_model'])

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=400)
        document_chunks = text_splitter.split_documents(documents)
        vector_db = await Chroma.afrom_documents(document_chunks, embedding_model,
                                                 client_settings=Settings(anonymized_telemetry=False))
    return chat_model, vector_db


async def get_message(message: types.Message, state: FSMContext, external_data=None):
    bot = external_data['bot'] if external_data else in_dp.bot
    database = external_data['database'] if external_data else in_database
    assistant = external_data['assistant'] if external_data else in_dp.assistant
    chat_model = external_data['chat_model'] if external_data else in_dp.chat_model
    vector_db = external_data['vector_db'] if external_data else in_dp.vector_db

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    thread = (await state.get_data()).get('thread', {})
    thread[str(message.chat.id)] = thread.get(str(message.chat.id), [])

    prompt = "System: " + (assistant["instruction"] or '') + "\n\n"

    for role, text in thread[str(message.chat.id)][-5:]:
        prompt += f"{role}: {text}\n"

    if vector_db:
        retrieved_docs = await vector_db.asimilarity_search(message.text, k=5)
        prompt += "\nDocuments: " + " ".join([doc.page_content for doc in retrieved_docs]) + "\n"

        prompt += ("\nSystem: Старайся дать ответ, в котором имеется полная информация об обсуждаемом объекте, "
                   "поскольку позже в Documents может не быть нужной тебе информации. "
                   "Если же предоставишь полную информацию, то сможешь найти ее в истории беседы.\n")

    prompt += f"\nHuman: {message.md_text}\n\nAssistant: "
    with open(f'core/assistant/internal_core/static/{assistant["id"]}/prompt.log', 'w') as f:
        f.write(prompt)

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    response = chat_model.invoke(prompt)
    price = await calc_price(response.response_metadata)
    user = await database.get_users(assistant['user_id'])
    await database.update_user(assistant['user_id'], {'balance': user['balance'] - price})
    await check_balance(user, database)
    thread[str(message.chat.id)].extend([("Human", message.md_text), ("Assistant", response.content)])
    await database.add_message(message.chat.id, assistant['id'], 'User', message.md_text)
    await database.add_message(message.chat.id, assistant['id'], 'Assistant', response.content,
                               price=price, model=assistant['model'])
    await state.update_data(thread=thread)
    try:
        for fr, to in [('_*', '<i>'), ('*_', '</i>'), ('<think>', '<i>'), ('</think>', '</i>')]:
            response.content = response.content.replace(fr, to)
        await message.answer(response.content, parse_mode='HTML')
    except:
        await message.answer(response.content, parse_mode=None)

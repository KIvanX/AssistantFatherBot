
import os
from aiogram import types
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from chromadb.config import Settings
from langchain_community.chat_models import GigaChat
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import database as in_database
from .custom_models import JinaEmbeddings
from .config import dp as in_dp


async def init_assistant(external_data=None):
    database = external_data['database'] if external_data else in_database
    assistant = external_data['assistant'] if external_data else in_dp.assistant

    if 'gigachat' in assistant["model"].lower():
        chat_model = GigaChat(credentials=os.environ['GIGACHAT_API_KEY'], model=assistant["model"],
                              verify_ssl_certs=False)
    elif 'gpt' in assistant["model"].lower():
        chat_model = ChatOpenAI(api_key=os.environ['OPENAI_API_KEY'], model=assistant["model"])
    else:
        chat_model = ChatGroq(temperature=0.6, model_name=assistant["model"], api_key=os.environ['GROQ_API_KEY'])

    documents = []
    for doc in await database.get_documents(assistant['id']):
        path = f'core/assistant/internal_core/static/{assistant["id"]}/documents/' + doc['file_name']
        documents.extend(TextLoader(path).load())

    embedding_model = JinaEmbeddings(token=os.environ['JINA_API_KEY'])
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=400)
    document_chunks = text_splitter.split_documents(documents)
    vector_db = Chroma.from_documents(document_chunks, embedding_model,
                                      client_settings=Settings(anonymized_telemetry=False)) if documents else None
    return chat_model, vector_db


async def get_message(message: types.Message, state: FSMContext, external_data=None):
    bot = external_data['bot'] if external_data else in_dp.bot
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
        retrieved_docs = vector_db.similarity_search(message.text, k=5)
        prompt += "\nDocuments: " + " ".join([doc.page_content for doc in retrieved_docs]) + "\n"

    prompt += ("\nSystem: Старайся дать ответ, в котором имеется полная информация об обсуждаемом объекте,"
               "поскольку позже в Documents может не быть нужной тебе информации. "
               "Если же предоставишь полную информацию, то сможешь найти ее в истории беседы.\n\n")

    prompt += f"\nHuman: {message.text}\n\nAssistant: "
    with open(f'core/assistant/internal_core/static/{assistant["id"]}/prompt.log', 'w') as f:
        f.write(prompt)

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    response = chat_model.invoke(prompt).content
    thread[str(message.chat.id)].extend([("Human", message.text), ("Assistant", response)])
    await state.update_data(thread=thread)
    await message.answer(response)

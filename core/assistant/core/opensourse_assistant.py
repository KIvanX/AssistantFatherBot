
import os

import redis
from aiogram import types
from aiogram.enums import ChatAction
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from annoy import AnnoyIndex
from core import database
from core.config import dp


async def init_opensource_assistant():
    dp.redis_client = redis.Redis(host='localhost', port=6379, db=8)
    dp.embed_model = OpenAIEmbeddings()
    dp.chat_model = ChatGroq(temperature=0, model_name=dp.assistant["model"], api_key=os.environ['GROQ_API_KEY'])
    dp.store = {}

    index = AnnoyIndex(1536, 'angular')
    splitter = CharacterTextSplitter(separator=" ", chunk_size=2000, chunk_overlap=500)

    k = 0
    for doc in await database.get_documents(dp.assistant['id']):
        with open(f'core/static/{dp.assistant["id"]}/documents/' + doc['file_name']) as f:
            doc_text = f.read()

        for chunk in splitter.split_text(doc_text):
            dp.redis_client.set(f'doc_{dp.assistant["id"]}_{k}', chunk)
            embedding = dp.embed_model.embed_query(chunk)
            index.add_item(k, embedding)
            k += 1

    index.build(10)
    index.save(f'core/static/{dp.assistant["id"]}/embedding_index.ann')


def get_session_history(session_id: int) -> BaseChatMessageHistory:
    if session_id not in dp.store:
        dp.store[session_id] = ChatMessageHistory()
    return dp.store[session_id]


async def get_message_opensource(message: types.Message):
    await dp.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", dp.assistant["instruction"]),
            MessagesPlaceholder(variable_name="history"),
            ("human", "documents: {documents}"),
            ("human", "{input}")
        ]
    )

    output_parser = StrOutputParser()
    chain = prompt | dp.chat_model | output_parser

    chain_with_message_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )

    retrieved_docs = search_similar_documents(message)
    response = chain_with_message_history.invoke(
        {"input": message.text, "documents": retrieved_docs},
        config={"configurable": {"session_id": message.chat.id}}
    )

    await message.answer(response)


def search_similar_documents(message: types.Message):
    index = AnnoyIndex(1536, 'angular')
    index.load(f'core/static/{dp.assistant["id"]}/embedding_index.ann')

    history = get_session_history(message.chat.id).messages
    context_messages = [msg.content for msg in history[-5:]] + [message.text]
    user_embedding = dp.embed_model.embed_query("\n".join(context_messages))
    neighbor_ids = index.get_nns_by_vector(user_embedding, 6)

    retrieved_docs = [dp.redis_client.get(f'doc_{dp.assistant["id"]}_{i}').decode('utf-8') for i in neighbor_ids]
    return retrieved_docs

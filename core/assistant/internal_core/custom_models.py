
import requests
from langchain_community.chat_models import GigaChat
from langchain_core.embeddings import Embeddings
# from sentence_transformers import SentenceTransformer
# import torch


class JinaEmbeddings(Embeddings):
    def __init__(self, token, embedding_model):
        self.url = 'https://api.jina.ai/v1/embeddings'

        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        }

        self.data = {
            "model": embedding_model,
            "task": "text-matching",
            "late_chunking": False,
            "dimensions": 1024,
            "embedding_type": "float",
        }

    def embed_documents(self, texts):
        self.data['input'] = texts
        response = requests.post(self.url, headers=self.headers, json=self.data)

        if response.status_code == 200 and response.json().get('data'):
            return [e['embedding'] for e in response.json()['data']]
        else:
            print(response.status_code, response.text)
            return []

    def embed_query(self, text):
        self.data['input'] = [text]
        response = requests.post(self.url, headers=self.headers, json=self.data)

        if response.status_code == 200 and response.json().get('data'):
            return response.json()['data'][0]['embedding']
        else:
            print(response.status_code, response.text)
            return {}


# class LocalEmbeddings(Embeddings):
#     def __init__(self, embedding_model='sentence-transformers/all-MiniLM-L12-v2'):
#         self.model = SentenceTransformer(embedding_model, device='cpu')
#         torch.set_num_threads(1)
#
#     def embed_documents(self, texts: list[str]):
#         return [e.astype(float).tolist() for e in self.model.encode(texts)]
#
#     def embed_query(self, text: str):
#         return self.model.encode([text])[0].astype(float).tolist()


class NlpCloudEmbeddings(Embeddings):
    def __init__(self, token, model_name="paraphrase-multilingual-mpnet-base-v2"):
        # self.client = nlpcloud.Client(model_name, token)
        self.client = None

    def embed_documents(self, texts):
        print(texts)
        print(self.client.embeddings(texts))
        return []

    def embed_query(self, text):
        return self.client.embeddings([text])['embeddings'][0]


class GigaChatModel:
    def __init__(self, token, model):
        self.model = GigaChat(credentials=token, model=model, verify_ssl_certs=False)

    def invoke(self, query):
        return self.model.invoke(query)


class ChatEdenAI:
    def __init__(self, api_key, provider, model, temperature=0.2, max_tokens=1000):
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, prompt: str) -> str:
        url = "https://api.edenai.run/v2/text/chat"

        payload = {
            "response_as_dict": True,
            "attributes_as_list": False,
            "show_base_64": True,
            "show_original_response": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tool_choice": "auto",
            "providers": [f'{self.provider}/{self.model}'],
            "text": prompt
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key}"
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to invoke model: {response.text}")

        data = response.json()
        return ChatEdenAIResponse(data)


class ChatEdenAIResponse:
    def __init__(self, data: dict):
        model = list(data.keys())[0]
        metadata = {'model_name': model.split('/')[1], 'token_usage': data[model]['original_response']['usage']}
        self.content = data[model].get('generated_text', '')
        self.response_metadata = metadata


class JinaEdenAIEmbeddings(Embeddings):
    def __init__(self, embedding_model='sentence-transformers/all-MiniLM-L12-v2'):
        pass

    def embed_documents(self, texts: list[str]):
        pass

    def embed_query(self, text: str):
        pass


# embedding_function = GigaChatEmbeddings(credentials=os.environ['GIGACHAT_API_KEY'], verify_ssl_certs=False)

# embedding_function = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")

# embedding_function = NlpCloudEmbeddings(token="4db2205d854d917321e0a6329b0a70725702cefa")

# embedding_function = JinaEmbeddings(token=os.environ['JINA_API_KEY'])

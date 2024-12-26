# import nlpcloud
import requests
from langchain_community.chat_models import GigaChat
from langchain_core.embeddings import Embeddings


class JinaEmbeddings(Embeddings):
    def __init__(self, token):
        self.url = 'https://api.jina.ai/v1/embeddings'

        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        }

        self.data = {
            "model": "jina-embeddings-v3",
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


# embedding_function = OpenAIEmbeddings(openai_api_key=os.environ['OPENAI_API_KEY'], model="text-embedding-ada-002")

# embedding_function = GigaChatEmbeddings(credentials=os.environ['GIGACHAT_API_KEY'], verify_ssl_certs=False)

# embedding_function = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")

# embedding_function = NlpCloudEmbeddings(token="4db2205d854d917321e0a6329b0a70725702cefa")

# embedding_function = JinaEmbeddings(token=os.environ['JINA_API_KEY'])

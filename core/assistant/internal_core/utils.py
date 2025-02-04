import logging
import os
import signal
import sys

price = {
    "gpt-4o-2024-11-20": {"input_cost": 1.25, "output_cost": 5},
    "gpt-4o-2024-08-06": {"input_cost": 1.25, "output_cost": 5},
    "gpt-4o": {"input_cost": 1.25, "output_cost": 5},

    "gpt-4-turbo-2024-04-09": {"input_cost": 5, "output_cost": 15},
    "gpt-4-turbo": {"input_cost": 5, "output_cost": 15},

    "gpt-4-0613": {"input_cost": 15, "output_cost": 30},
    "gpt-4": {"input_cost": 15, "output_cost": 30},

    "gpt-4o-mini-2024-07-18": {"input_cost": 0.075, "output_cost": 0.3},
    "gpt-4o-mini": {"input_cost": 0.075, "output_cost": 0.3},

    "gpt-3.5-turbo-0125": {"input_cost": 0.25, "output_cost": 0.75},
    "gpt-3.5-turbo": {"input_cost": 0.25, "output_cost": 0.75},

    "claude-3-5-haiku-latest": {"input_cost": 1, "output_cost": 5},
    "claude-3-5-sonnet-latest": {"input_cost": 3, "output_cost": 15},
    "claude-3-opus-latest": {"input_cost": 15, "output_cost": 75},

    "GigaChat": {"input_cost": 0, "output_cost": 1000},
    "GigaChat:1.0.26.20": {"input_cost": 0, "output_cost": 1000},

    "GigaChat-Pro": {"input_cost": 0, "output_cost": 7275},
    "GigaChat-Pro:1.0.26.20": {"input_cost": 0, "output_cost": 7275},

    "GigaChat-Max": {"input_cost": 0, "output_cost": 7566},
    "GigaChat-Max:1.0.26.20": {"input_cost": 0, "output_cost": 7566}
}

emb_price = {'jina-clip-v2': 0,
             'jina-embeddings-v3': 0,
             'text-embedding-3-small': 0.01,
             'text-embedding-3-large': 0.065,
             'text-embedding-ada-002': 0.05}


async def calc_price(params: dict):
    model = params['model_name']

    if model not in price:
        if paid_model(model):
            print(f"Model {model} not found in price list")
        return 0

    if 'gpt' in model or 'claude' in model:
        course = 100
        input_cost = params['token_usage']['prompt_tokens'] * price[model]['input_cost'] / 1_000_000 * course
        output_cost = params['token_usage']['completion_tokens'] * price[model]['output_cost'] / 1_000_000 * course
    else:
        input_cost = 0
        output_cost = params['token_usage'].total_tokens * price[model]['output_cost'] / 5_000_000

    return input_cost + output_cost


async def check_balance(user: dict, database):
    if user['balance'] <= 0:
        for assistant in await database.get_assistants(user['id']):
            if paid_model(assistant['model'].lower()):
                if assistant['pid']:
                    try:
                        os.kill(assistant['pid'], signal.SIGTERM)
                    except:
                        pass
                await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})


def paid_model(model: str) -> bool:
    model = model.lower()
    return 'gpt' in model or 'gigachat' in model or 'claude' in model


def init_logging():
    if os.environ.get('DEBUG', '').lower() == 'false':
        logging.root.handlers.clear()
        logging.basicConfig(level=logging.WARNING,
                            filename=f"core/static/logs.log",
                            filemode="a",
                            handlers=[logging.FileHandler("core/static/logs.log")],
                            format=f"ASSISTANT {os.environ.get('ASSISTANT_ID')} %(asctime)s %(levelname)s "
                                   f"%(message)s\n" + '_' * 100)

    def log_unhandled_exception(exc_type, exc_value, exc_traceback):
        logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = log_unhandled_exception

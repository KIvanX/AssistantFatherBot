import os
import signal

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

        "GigaChat": {"input_cost": 0, "output_cost": 1000},
        "GigaChat:1.0.26.20": {"input_cost": 0, "output_cost": 1000},

        "GigaChat-Pro": {"input_cost": 0, "output_cost": 7275},
        "GigaChat-Pro:1.0.26.20": {"input_cost": 0, "output_cost": 7275},

        "GigaChat-Max": {"input_cost": 0, "output_cost": 7566},
        "GigaChat-Max:1.0.26.20": {"input_cost": 0, "output_cost": 7566},
    }


async def calc_price(params: dict):
    model = params['model_name']

    if model not in price:
        if 'gpt' in model.lower() or 'gigachat' in model.lower():
            print(f"Model {model} not found in price list")
        return 0

    if 'gpt' in model:
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
            if 'gpt' in assistant['model'].lower() or 'gigachat' in assistant['model'].lower():
                if assistant['pid']:
                    try:
                        os.kill(assistant['pid'], signal.SIGTERM)
                    except:
                        pass
                await database.update_assistant(assistant['id'], {'pid': None, 'status': 'stopped'})

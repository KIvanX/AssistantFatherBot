from aiogram.fsm.state import StatesGroup, State


class BaseAssistantStates(StatesGroup):
    in_panel = State()
    auto_create = State()
    top_up_balance = State()


class CreateAssistantStates(StatesGroup):
    token = State()


class EditAssistantStates(StatesGroup):
    edit = State()
    parameter = State()
    edit_token = State()


class KnowledgeBaseAssistantStates(StatesGroup):
    add = State()
    delete = State()

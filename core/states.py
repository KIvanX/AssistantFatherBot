from aiogram.fsm.state import StatesGroup, State


class CreateAssistantStates(StatesGroup):
    token = State()


class EditAssistantStates(StatesGroup):
    edit = State()
    parameter = State()
    edit_token = State()


class KnowledgeBaseAssistantStates(StatesGroup):
    add = State()
    delete = State()

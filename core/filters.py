from aiogram.filters.callback_data import CallbackData


class SelectAssistant(CallbackData, prefix="SA"):
    id: int


class DeleteDocument(CallbackData, prefix="DD"):
    id: int

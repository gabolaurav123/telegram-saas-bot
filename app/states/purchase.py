from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    waiting_for_proof = State()


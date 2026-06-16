"""utils/states.py — FSM state groups for aiogram 3."""
from aiogram.fsm.state import State, StatesGroup


class SubmitPost(StatesGroup):
    choosing_type  = State()
    entering_title = State()
    entering_body  = State()
    entering_tags  = State()
    entering_opts  = State()   # poll options only
    confirming     = State()


class SearchFlow(StatesGroup):
    choosing_mode  = State()
    entering_query = State()


class FaqFlow(StatesGroup):
    asking         = State()


class AdminFaq(StatesGroup):
    entering_question = State()
    entering_answer   = State()
    entering_keywords = State()
    editing_id        = State()   # stored in FSM data
    editing_question  = State()
    editing_answer    = State()
    editing_keywords  = State()


class AdminClub(StatesGroup):
    waiting_video     = State()
    entering_title    = State()
    entering_desc     = State()
    entering_tags     = State()


class AdminMisc(StatesGroup):
    entering_user_id  = State()   # set_admin / set_club

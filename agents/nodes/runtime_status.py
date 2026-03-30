from __future__ import annotations

from agents.constants import StateKey
from agents.state import AgentState


def check_runtime_cancel(state: AgentState) -> None:
    checker = state.get(StateKey.RUNTIME_CANCEL_CHECK)
    if callable(checker):
        checker()


def notify_runtime_progress(state: AgentState, step: str) -> None:
    check_runtime_cancel(state)
    callback = state.get(StateKey.RUNTIME_PROGRESS_CALLBACK)
    if callable(callback):
        callback(step)

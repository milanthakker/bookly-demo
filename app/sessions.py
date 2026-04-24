from dataclasses import dataclass
from typing import Optional

@dataclass
class Session:
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    active_order_id: Optional[int] = None

_store: dict[str, Session] = {}


def get_or_create(session_id: str) -> Session:
    if session_id not in _store:
        _store[session_id] = Session()
    return _store[session_id]


def update(session_id: str, **kwargs):
    session = get_or_create(session_id)
    for key, value in kwargs.items():
        if value is not None:
            setattr(session, key, value)

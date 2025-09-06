from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from mobasher.storage.db import get_session, init_engine


def get_db() -> Generator[Session, None, None]:
    # Ensure engine initialized
    init_engine()
    yield from get_session()



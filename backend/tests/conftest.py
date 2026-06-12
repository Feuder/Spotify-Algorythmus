import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

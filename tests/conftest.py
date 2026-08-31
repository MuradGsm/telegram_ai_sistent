from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.conf import settings
from app.core.security import create_access_token, hash_password_async
from app.db.database import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegister

assert settings.test_database_url.endswith("_test"), (
    "test_database_url должен указывать на отдельную *_test БД"
)

test_engine = create_async_engine(settings.test_database_url, poolclass=NullPool)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_schema() -> AsyncIterator[None]:
    async with test_engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
    yield
    async with test_engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.commit()
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    repo = UserRepository(db_session)
    hashed = await hash_password_async("TestPass123!")
    user = await repo.create(
        UserRegister(email="user@example.com", password="TestPass123!", full_name="Test User"),
        hashed,
    )
    await db_session.flush()
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    repo = UserRepository(db_session)
    hashed = await hash_password_async("OtherPass123!")
    user = await repo.create(
        UserRegister(email="other@example.com", password="OtherPass123!", full_name="Other User"),
        hashed,
    )
    await db_session.flush()
    return user


@pytest.fixture
def other_auth_headers(other_user: User) -> dict[str, str]:
    token = create_access_token(other_user.id)
    return {"Authorization": f"Bearer {token}"}
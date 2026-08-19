from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import UserRegister


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, payload: UserRegister, hashed_password: str) -> User:
        user = User(
            email=payload.email,
            hashed_password = hashed_password,
            full_name = payload.full_name
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user
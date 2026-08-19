from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister
)
from app.services.auth_service import AuthService


router = APIRouter(prefix='/auth', tags=['auth'])


def get_auth_service(db: AsyncSession =Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, service: AuthService = Depends(get_auth_service)) -> User:
    return await service.register(payload)


@router.post('/login', response_model=TokenPair)
async def login(payload: UserLogin, service: AuthService = Depends(get_auth_service)) -> TokenPair:
    return await service.login(payload)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, service: AuthService = Depends(get_auth_service)) -> TokenPair:
    return await service.refresh(payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
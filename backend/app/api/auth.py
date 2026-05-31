"""
认证相关 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import aiosqlite

from app.config import get_settings
from app.database import DATABASE_PATH

router = APIRouter()
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class UserCreate(BaseModel):
    """用户注册请求"""
    username: str
    email: str
    password: str
    github_token: Optional[str] = None


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    github_token: Optional[str]


class Token(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    """用户注册"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # 检查用户名是否已存在
        cursor = await db.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (user.username, user.email),
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

        # 创建用户
        hashed_password = pwd_context.hash(user.password)
        cursor = await db.execute(
            "INSERT INTO users (username, email, hashed_password, github_token) VALUES (?, ?, ?, ?)",
            (user.username, user.email, hashed_password, user.github_token),
        )
        await db.commit()
        user_id = cursor.lastrowid

        return UserResponse(
            id=user_id,
            username=user.username,
            email=user.email,
            github_token=user.github_token,
        )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, hashed_password FROM users WHERE username = ?",
            (form_data.username,),
        )
        user = await cursor.fetchone()

        if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["id"])},
            expires_delta=access_token_expires,
        )

        return {"access_token": access_token, "token_type": "bearer"}


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """从 JWT Token 获取当前用户"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, github_token FROM users WHERE id = ?",
            (int(user_id),),
        )
        user = await cursor.fetchone()
        if user is None:
            raise credentials_exception
        return dict(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        github_token=current_user.get("github_token"),
    )

from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Annotated
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

app = FastAPI()

# Настройки для JWT
SECRET_KEY = "a_very_secret_key"  # В реальном проекте используйте безопасный секрет
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 48

# Хэширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Схема для Bearer токена
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

# Модели
class User(BaseModel):
    id: int
    username: str
    hashed_password: str
    group: str  # 'user' or 'admin'

class UserOut(BaseModel):
    id: int
    username: str
    group: str

class UserCreate(BaseModel):
    username: str
    password: str
    group: Optional[str] = "user"  # По умолчанию 'user'

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    group: Optional[str] = None

class Login(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class Advertisement(BaseModel):
    id: int
    title: str
    description: str
    price: float
    author_id: int  # Изменено на author_id для связи с пользователем
    created_at: datetime

class AdvertisementCreate(BaseModel):
    title: str
    description: str
    price: float

class AdvertisementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

# In-memory storage
users: List[User] = []
user_id_counter = 1

advertisements: List[Advertisement] = []
ad_id_counter = 1

# Вспомогательные функции
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Optional[UserOut]:
    if not token:
        return None
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        group: str = payload.get("group")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = next((UserOut(id=u.id, username=u.username, group=u.group) for u in users if u.id == user_id), None)
    if user is None:
        raise credentials_exception
    return user

# Роут для логина
@app.post("/login", response_model=Token)
async def login_for_access_token(login_data: Login):
    user = next((u for u in users if u.username == login_data.username), None)
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": user.id, "group": user.group}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Роуты для пользователей
@app.post("/user", response_model=UserOut)
async def create_user(user_create: UserCreate, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    # Неавторизованные могут создавать только 'user', админы - любые
    if current_user and current_user.group == "admin":
        pass  # Админ может создать любого
    else:
        if user_create.group != "user":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create admins")
    if any(u.username == user_create.username for u in users):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    global user_id_counter
    new_user = User(
        id=user_id_counter,
        username=user_create.username,
        hashed_password=get_password_hash(user_create.password),
        group=user_create.group
    )
    users.append(new_user)
    user_id_counter += 1
    return UserOut(id=new_user.id, username=new_user.username, group=new_user.group)

@app.get("/user/{user_id}", response_model=UserOut)
async def get_user(user_id: int):
    # Доступно всем
    user = next((UserOut(id=u.id, username=u.username, group=u.group) for u in users if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@app.patch("/user/{user_id}", response_model=UserOut)
async def update_user(user_id: int, user_update: UserUpdate, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = next((u for u in users if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.group == "admin" or current_user.id == user_id:
        if user_update.username is not None:
            user.username = user_update.username
        if user_update.password is not None:
            user.hashed_password = get_password_hash(user_update.password)
        if user_update.group is not None:
            if current_user.group != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can change group")
            user.group = user_update.group
        return UserOut(id=user.id, username=user.username, group=user.group)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

@app.delete("/user/{user_id}")
async def delete_user(user_id: int, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_index = next((i for i, u in enumerate(users) if u.id == user_id), None)
    if user_index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.group == "admin" or current_user.id == user_id:
        del users[user_index]
        # Удаляем объявления пользователя
        global advertisements
        advertisements = [ad for ad in advertisements if ad.author_id != user_id]
        return {"detail": "User deleted"}
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

# Роуты для объявлений (адаптированные с правами)
@app.post("/advertisement", response_model=Advertisement)
async def create_advertisement(ad: AdvertisementCreate, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    # User и admin могут создавать
    global ad_id_counter
    new_ad = Advertisement(
        id=ad_id_counter,
        title=ad.title,
        description=ad.description,
        price=ad.price,
        author_id=current_user.id,
        created_at=datetime.now(timezone.utc)
    )
    advertisements.append(new_ad)
    ad_id_counter += 1
    return new_ad

@app.patch("/advertisement/{advertisement_id}", response_model=Advertisement)
async def update_advertisement(advertisement_id: int, ad_update: AdvertisementUpdate, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    ad = next((a for a in advertisements if a.id == advertisement_id), None)
    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")
    if current_user.group == "admin" or ad.author_id == current_user.id:
        if ad_update.title is not None:
            ad.title = ad_update.title
        if ad_update.description is not None:
            ad.description = ad_update.description
        if ad_update.price is not None:
            ad.price = ad_update.price
        return ad
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

@app.delete("/advertisement/{advertisement_id}")
async def delete_advertisement(advertisement_id: int, current_user: Annotated[Optional[UserOut], Depends(get_current_user)]):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    ad_index = next((i for i, a in enumerate(advertisements) if a.id == advertisement_id), None)
    if ad_index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")
    ad = advertisements[ad_index]
    if current_user.group == "admin" or ad.author_id == current_user.id:
        del advertisements[ad_index]
        return {"detail": "Advertisement deleted"}
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

@app.get("/advertisement/{advertisement_id}", response_model=Advertisement)
async def get_advertisement(advertisement_id: int):
    # Доступно всем
    ad = next((a for a in advertisements if a.id == advertisement_id), None)
    if not ad:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found")
    return ad

@app.get("/advertisement", response_model=List[Advertisement])
async def search_advertisements(
    title: Optional[str] = None,
    description: Optional[str] = None,
    price: Optional[float] = None,
    author_id: Optional[int] = None,  # Добавлено для поиска по автору, если нужно
    created_at: Optional[datetime] = None
):
    # Доступно всем
    results = advertisements
    if title:
        results = [ad for ad in results if title.lower() in ad.title.lower()]
    if description:
        results = [ad for ad in results if description.lower() in ad.description.lower()]
    if price is not None:
        results = [ad for ad in results if ad.price == price]
    if author_id is not None:
        results = [ad for ad in results if ad.author_id == author_id]
    if created_at:
        results = [ad for ad in results if ad.created_at.date() == created_at.date()]
    return results
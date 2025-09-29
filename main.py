from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update, delete

app = FastAPI()

# Настройки БД (будут браться из переменных окружения в Docker)
DATABASE_URL = "postgresql://user:password@db:5432/ad_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class AdvertisementDB(Base):
    __tablename__ = "advertisements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    author = Column(String, index=True)
    created_at = Column(DateTime, default=func.now())


Base.metadata.create_all(bind=engine)


class Advertisement(BaseModel):
    id: int
    title: str
    description: str
    price: float
    author: str
    created_at: datetime


class AdvertisementCreate(BaseModel):
    title: str
    description: str
    price: float
    author: str


class AdvertisementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    author: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/advertisement", response_model=Advertisement)
def create_advertisement(ad: AdvertisementCreate):
    db = SessionLocal()
    try:
        # Проверка на дубликат (title + author уникальны)
        stmt = select(AdvertisementDB).where(
            AdvertisementDB.title == ad.title,
            AdvertisementDB.author == ad.author
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="Advertisement with this title and author already exists")

        new_ad = AdvertisementDB(
            title=ad.title,
            description=ad.description,
            price=ad.price,
            author=ad.author
        )
        db.add(new_ad)
        db.commit()
        db.refresh(new_ad)
        return new_ad
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        db.close()


@app.patch("/advertisement/{advertisement_id}", response_model=Advertisement)
def update_advertisement(advertisement_id: int, ad_update: AdvertisementUpdate):
    db = SessionLocal()
    try:
        stmt = select(AdvertisementDB).where(AdvertisementDB.id == advertisement_id)
        ad = db.execute(stmt).scalars().first()
        if not ad:
            raise HTTPException(status_code=404, detail="Advertisement not found")

        update_data = ad_update.dict(exclude_unset=True)
        if update_data:
            db.execute(update(AdvertisementDB).where(AdvertisementDB.id == advertisement_id).values(**update_data))
            db.commit()
            db.refresh(ad)
        return ad
    finally:
        db.close()


@app.delete("/advertisement/{advertisement_id}")
def delete_advertisement(advertisement_id: int):
    db = SessionLocal()
    try:
        stmt = select(AdvertisementDB).where(AdvertisementDB.id == advertisement_id)
        ad = db.execute(stmt).scalars().first()
        if not ad:
            raise HTTPException(status_code=404, detail="Advertisement not found")

        db.execute(delete(AdvertisementDB).where(AdvertisementDB.id == advertisement_id))
        db.commit()
        return {"detail": "Advertisement deleted"}
    finally:
        db.close()


@app.get("/advertisement/{advertisement_id}", response_model=Advertisement)
def get_advertisement(advertisement_id: int):
    db = SessionLocal()
    try:
        stmt = select(AdvertisementDB).where(AdvertisementDB.id == advertisement_id)
        ad = db.execute(stmt).scalars().first()
        if not ad:
            raise HTTPException(status_code=404, detail="Advertisement not found")
        return ad
    finally:
        db.close()


@app.get("/advertisement", response_model=List[Advertisement])
def search_advertisements(
        title: Optional[str] = Query(None),
        description: Optional[str] = Query(None),
        price: Optional[float] = Query(None),
        author: Optional[str] = Query(None),
        created_at: Optional[datetime] = Query(None)
):
    db = SessionLocal()
    try:
        stmt = select(AdvertisementDB)
        if title:
            stmt = stmt.where(AdvertisementDB.title.ilike(f"%{title}%"))
        if description:
            stmt = stmt.where(AdvertisementDB.description.ilike(f"%{description}%"))
        if price is not None:
            stmt = stmt.where(AdvertisementDB.price == price)
        if author:
            stmt = stmt.where(AdvertisementDB.author.ilike(f"%{author}%"))
        if created_at:
            stmt = stmt.where(AdvertisementDB.created_at == created_at)  # Точное совпадение с временем
        results = db.execute(stmt).scalars().all()
        return results
    finally:
        db.close()
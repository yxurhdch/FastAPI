from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

app = FastAPI()

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

# In-memory storage
advertisements = []
ad_id_counter = 1

@app.post("/advertisement", response_model=Advertisement)
def create_advertisement(ad: AdvertisementCreate):
    global ad_id_counter
    new_ad = Advertisement(
        id=ad_id_counter,
        title=ad.title,
        description=ad.description,
        price=ad.price,
        author=ad.author,
        created_at=datetime.now()
    )
    advertisements.append(new_ad)
    ad_id_counter += 1
    return new_ad

@app.patch("/advertisement/{advertisement_id}", response_model=Advertisement)
def update_advertisement(advertisement_id: int, ad_update: AdvertisementUpdate):
    for ad in advertisements:
        if ad.id == advertisement_id:
            if ad_update.title is not None:
                ad.title = ad_update.title
            if ad_update.description is not None:
                ad.description = ad_update.description
            if ad_update.price is not None:
                ad.price = ad_update.price
            if ad_update.author is not None:
                ad.author = ad_update.author
            return ad
    raise HTTPException(status_code=404, detail="Advertisement not found")

@app.delete("/advertisement/{advertisement_id}")
def delete_advertisement(advertisement_id: int):
    global advertisements
    advertisements = [ad for ad in advertisements if ad.id != advertisement_id]
    return {"detail": "Advertisement deleted"}

@app.get("/advertisement/{advertisement_id}", response_model=Advertisement)
def get_advertisement(advertisement_id: int):
    for ad in advertisements:
        if ad.id == advertisement_id:
            return ad
    raise HTTPException(status_code=404, detail="Advertisement not found")

@app.get("/advertisement", response_model=List[Advertisement])
def search_advertisements(
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    price: Optional[float] = Query(None),
    author: Optional[str] = Query(None),
    created_at: Optional[datetime] = Query(None)
):
    results = advertisements
    if title:
        results = [ad for ad in results if title.lower() in ad.title.lower()]
    if description:
        results = [ad for ad in results if description.lower() in ad.description.lower()]
    if price is not None:
        results = [ad for ad in results if ad.price == price]
    if author:
        results = [ad for ad in results if author.lower() in ad.author.lower()]
    if created_at:
        results = [ad for ad in results if ad.created_at.date() == created_at.date()]
    return results
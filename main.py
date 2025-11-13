import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId
from datetime import datetime, timezone

from database import db, create_document, get_documents
from schemas import Flashcard

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
    elif _id is not None and "id" not in doc:
        doc["id"] = str(_id)
    doc.pop("_id", None)
    # Ensure datetime is ISO strings
    for k, v in list(doc.items()):
        if isinstance(v, (datetime,)):
            doc[k] = v.astimezone(timezone.utc).isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Flashcard API
class FlashcardOut(BaseModel):
    id: str
    question: str
    answer: str
    deck: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@app.get("/api/flashcards", response_model=List[FlashcardOut])
def list_flashcards(deck: Optional[str] = None, tag: Optional[str] = None, limit: Optional[int] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    filter_dict: Dict[str, Any] = {}
    if deck:
        filter_dict["deck"] = deck
    if tag:
        filter_dict["tags"] = tag

    docs = get_documents("flashcard", filter_dict=filter_dict, limit=limit)
    return [FlashcardOut(**serialize_doc(d)) for d in docs]


@app.post("/api/flashcards", response_model=FlashcardOut)
def create_flashcard(card: Flashcard):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    inserted_id = create_document("flashcard", card)
    doc = db["flashcard"].find_one({"_id": ObjectId(inserted_id)})
    return FlashcardOut(**serialize_doc(doc))


@app.get("/api/flashcards/{card_id}", response_model=FlashcardOut)
def get_flashcard(card_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(card_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    doc = db["flashcard"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return FlashcardOut(**serialize_doc(doc))


@app.put("/api/flashcards/{card_id}", response_model=FlashcardOut)
def update_flashcard(card_id: str, card: Flashcard):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(card_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    update_data = card.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = db["flashcard"].update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    doc = db["flashcard"].find_one({"_id": oid})
    return FlashcardOut(**serialize_doc(doc))


@app.delete("/api/flashcards/{card_id}")
def delete_flashcard(card_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        oid = ObjectId(card_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = db["flashcard"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return {"success": True}


# Optional: expose schemas for viewers/tools
@app.get("/schema")
def get_schema():
    # Return a simple schema map for the defined models
    return {
        "flashcard": Flashcard.model_json_schema()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

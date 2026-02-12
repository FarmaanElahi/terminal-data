from fastapi import APIRouter

router = APIRouter(tags=["base"])


@router.get("/")
def read_root():
    return {"status": "ok", "message": "Terminal Data API is running"}

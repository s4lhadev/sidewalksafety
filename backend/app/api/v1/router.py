from fastapi import APIRouter
from app.api.v1.endpoints import auth, discovery, parking_lots, businesses, deals, usage

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(discovery.router, prefix="/discover", tags=["discovery"])
api_router.include_router(parking_lots.router, prefix="/parking-lots", tags=["parking-lots"])
api_router.include_router(businesses.router, prefix="/businesses", tags=["businesses"])
api_router.include_router(deals.router, prefix="/deals", tags=["deals"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])

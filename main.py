from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.features.distribution.dist_routes import router as dist_router

app = FastAPI(title="SBACEM Distribution Unifier")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.router import router as auth_router
from app.middleware import get_current_user
from fastapi import Depends

# ... (Previous middleware setup)

@app.get("/")
async def root():
    return {"message": "SBACEM API is running (Satellite Mode)"}

# Auth Routes (Public)
app.include_router(auth_router, prefix="/api", tags=["Authentication"])

# Protected Business Routes
app.include_router(
    dist_router, 
    prefix="/api", 
    dependencies=[Depends(get_current_user)]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

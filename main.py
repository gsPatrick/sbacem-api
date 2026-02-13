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

@app.get("/")
async def root():
    return {"message": "SBACEM API is running"}

app.include_router(dist_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

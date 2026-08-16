from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from db import supabase  # noqa: F401 — imported so it initializes early and routers can share it

app = FastAPI(title="Prism API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Prism API is running"}


from auth import router as auth_router
app.include_router(auth_router, prefix="/auth")

from uploads import router as uploads_router
app.include_router(uploads_router, prefix="/uploads")

from analysis import router as analysis_router
app.include_router(analysis_router, prefix="/analysis")

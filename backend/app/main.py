from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.frontend_data import router as frontend_data_router


app = FastAPI(title="World Cup 2026 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(frontend_data_router)


@app.get("/")
def health_check():
    return {"status": "ok"}

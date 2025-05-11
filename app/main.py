from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, users, maps, collections, markers, folders

app = FastAPI(title="Topotik API")
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def read_root():
    return {"message": "Hello, world!"}

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(maps.router, prefix="/maps", tags=["maps"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(markers.router, prefix="/markers", tags=["markers"])
app.include_router(folders.router, prefix="/folders", tags=["folders"])

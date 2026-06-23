from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Importamos el router desde la estructura de carpetas
from app.routers import dashboard
from app.routers import insumos
from app.routers import lotes


app = FastAPI(
    title="AgroTech API",
    description="API para el monitoreo inteligente e inventario agrícola - SENA ADSO",
    version="1.0.0"
)

# Configurar orígenes permitidos para conectar con React (Vite)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar el router del Dashboard
app.include_router(dashboard.router)
app.include_router(insumos.router)
app.include_router(lotes.router)

@app.get("/")
def read_root():
    return {"status": "AgroTech Backend Operando Correctamente"}
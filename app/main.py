from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Importamos el router desde la estructura de carpetas
from app.routers import dashboard
from app.routers import auth
from app.routers import insumos
from app.routers import lotes, movimientos
from app.routers import alertas, proyecciones
from app.routers import ventas
from app.database.database import engine


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
app.include_router(auth.router)
app.include_router(insumos.router)
app.include_router(lotes.router)
app.include_router(movimientos.router)
app.include_router(alertas.router)
app.include_router(proyecciones.router)
app.include_router(ventas.router)


@app.on_event("startup")
def ensure_sales_columns():
    columns = {
        "cliente_nombre": "VARCHAR(120) NULL",
        "cliente_nit": "VARCHAR(40) NULL",
        "subtotal_factura": "DECIMAL(10,2) NOT NULL DEFAULT 0",
        "descuento_porcentaje": "DECIMAL(5,2) NOT NULL DEFAULT 0",
        "descuento_valor": "DECIMAL(10,2) NOT NULL DEFAULT 0",
        "iva_porcentaje": "DECIMAL(5,2) NOT NULL DEFAULT 19",
        "iva_valor": "DECIMAL(10,2) NOT NULL DEFAULT 0",
        "total_factura": "DECIMAL(10,2) NOT NULL DEFAULT 0",
    }

    with engine.begin() as connection:
        for column_name, column_definition in columns.items():
            exists = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name = 'ventas'
                      AND column_name = :column_name
                    """
                ),
                {"column_name": column_name},
            ).scalar()

            if not exists:
                connection.execute(
                    text(f"ALTER TABLE ventas ADD COLUMN {column_name} {column_definition}")
                )


@app.get("/")
def read_root():
    return {"status": "AgroTech Backend Operando Correctamente"}

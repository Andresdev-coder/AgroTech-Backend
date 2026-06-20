from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==========================================
#  ESQUEMAS DEL DASHBOARD 
# ==========================================

class DashboardResponse(BaseModel):
    kpis: List[Dict[str, Any]]
    clima: Dict[str, Any]
    lotes_criticos: List[Dict[str, Any]]
    movimientos: List[Dict[str, Any]]
    estado_lotes: Dict[str, Any]


# ==========================================
#  ESQUEMAS DE INSUMOS (MÓDULO INVENTARIO)
# ==========================================

# Esquema base para los Insumos Agrícolas
class InsumoBase(BaseModel):
    nombre: str = Field(..., example="Fertilizante NPK 20-20-20")
    categoria: str = Field(..., example="Fertilizantes")  # Semillas, Fertilizantes, Pesticidas, etc.
    unidad_medida: str = Field(..., example="kg")          # kg, Litros, Unidades
    stock_minimo: float = Field(..., gte=0, example=10.0)

# Esquema para recibir datos desde el Frontend (Creación)
class InsumoCreate(InsumoBase):
    pass

# Esquema para responder con los datos completos desde la API
class InsumoResponse(InsumoBase):
    id: int
    stock_actual: float = Field(0.0, description="Suma total de las cantidades en todos los lotes activos")
    estado: str = Field("Seguro", description="Calculado dinámicamente: Seguro, Alerta o Crítico")
    fecha_creacion: datetime

    class Config:
        from_attributes = True
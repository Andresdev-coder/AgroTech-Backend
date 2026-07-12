from pydantic import BaseModel, Field, EmailStr
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
#  ESQUEMAS DE AUTENTICACIÓN
# ==========================================

class LoginRequest(BaseModel):
    correo: EmailStr = Field(..., example="admin@agrotech.com")
    contrasena: str = Field(..., min_length=6, example="admin123")


class UsuarioLogin(BaseModel):
    id_usuario: int
    nombre: str
    correo: EmailStr
    rol: str
    rol_nombre: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UsuarioLogin


class VentaCreate(BaseModel):
    id_lote: int
    cantidad: int = Field(..., gt=0)
    precio_unitario: float = Field(..., gt=0)


class VentaLineaCreate(BaseModel):
    id_lote: int
    cantidad: int = Field(..., gt=0)
    precio_unitario: float = Field(..., gt=0)


class VentaFacturaCreate(BaseModel):
    cliente_nombre: Optional[str] = None
    cliente_nit: Optional[str] = None
    descuento_porcentaje: float = Field(0, ge=0, le=100)
    iva_porcentaje: float = Field(19, ge=0, le=100)
    items: List[VentaLineaCreate]


class VentaResponse(BaseModel):
    id_venta: int
    fecha_venta: str
    vendedor: str
    producto: str
    lote: str
    cantidad: int
    precio_unitario: float
    subtotal: float
    stock_restante: int


class VentaFacturaResponse(BaseModel):
    message: str
    id_venta: int
    consecutivo: str
    vendedor: str
    fecha_venta: str
    cliente_nombre: Optional[str] = None
    cliente_nit: Optional[str] = None
    subtotal_factura: float
    descuento_porcentaje: float
    descuento_valor: float
    iva_porcentaje: float
    iva_valor: float
    total_factura: float
    items: List[VentaResponse]


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

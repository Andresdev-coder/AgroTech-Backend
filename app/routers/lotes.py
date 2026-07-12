from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import date
from typing import List
from app.core.dependencies import require_roles
from app.database.database import get_db  
import pymysql
from sqlalchemy import text

router = APIRouter(
    prefix="/api/lotes",
    tags=["Lotes"]
)

# Esquema de Pydantic para recibir los datos del Frontend
class LoteCreate(BaseModel):
    codigo_lote: str
    cantidad_inicial: int
    fecha_vencimiento: date
    id_producto: int

# Esquema para responder los datos ordenados
class LoteResponse(BaseModel):
    id_lote: int
    codigo_lote: str
    cantidad_inicial: int
    cantidad_actual: int
    fecha_vencimiento: date
    fecha_ingreso: str
    id_producto: int

    class Config:
        from_attributes = True

# 1. ENDPOINT: Obtener los lotes de un producto específico
@router.get("/{id_producto}", response_model=List[dict], dependencies=[Depends(require_roles("admin", "bodeguero", "ventas"))])
def obtener_lotes_por_producto(id_producto: int, connection = Depends(get_db)):
    try:
        # En SQLAlchemy, las consultas crudas se envuelven con text() 
        # y se ejecutan directamente desde la sesión usando connection.execute()
        sql = text("""
            SELECT id_lote, codigo_lote, cantidad_inicial, cantidad_actual, 
                   fecha_vencimiento, DATE_FORMAT(fecha_ingreso, '%Y-%m-%d %H:%i') as fecha_ingreso, id_producto
            FROM lotes
            WHERE id_producto = :id_producto
            ORDER BY fecha_vencimiento ASC;
        """)
        
        # Ejecutamos la consulta pasando el parámetro mapeado (:id_producto)
        resultado = connection.execute(sql, {"id_producto": id_producto})
        
        # Mapeamos los resultados a un diccionario dinámico para que coincida con List[dict]
        lotes = [dict(row._mapping) for row in resultado.fetchall()]
        return lotes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar la base de datos: {str(e)}")

# 2. ENDPOINT: Registrar un nuevo lote físico
@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "bodeguero"))])
def crear_lote(lote: LoteCreate, connection = Depends(get_db)):
    try:
        # 1. Verificar si el código de lote ya existe usando text()
        sql_check = text("SELECT id_lote FROM lotes WHERE codigo_lote = :codigo_lote")
        result_check = connection.execute(sql_check, {"codigo_lote": lote.codigo_lote})
        
        if result_check.fetchone():
            raise HTTPException(
                status_code=400, 
                detail=f"El código de lote '{lote.codigo_lote}' ya se encuentra registrado."
            )

        # 2. Insertar el lote (cantidad_actual inicia igual a cantidad_inicial)
        sql_insert = text("""
            INSERT INTO lotes (codigo_lote, cantidad_inicial, cantidad_actual, fecha_vencimiento, id_producto)
            VALUES (:codigo_lote, :cantidad_inicial, :cantidad_actual, :fecha_vencimiento, :id_producto);
        """)
        
        connection.execute(sql_insert, {
            "codigo_lote": lote.codigo_lote,
            "cantidad_inicial": lote.cantidad_inicial,
            "cantidad_actual": lote.cantidad_inicial,  # Inicia siendo la misma
            "fecha_vencimiento": lote.fecha_vencimiento,
            "id_producto": lote.id_producto
        })
        
        # Guardamos los cambios de forma explícita en la base de datos
        connection.commit()
        return {"message": "Lote registrado exitosamente e inventario actualizado."}
            
    except HTTPException as http_exc:
        # Si es un error controlado (como el 400 de arriba), lo dejamos pasar tal cual
        raise http_exc
    except Exception as e:
        # Si algo falla a nivel de base de datos, hacemos rollback para limpiar la sesión
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {str(e)}")

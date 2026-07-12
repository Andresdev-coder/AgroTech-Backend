from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
from app.core.dependencies import require_roles
from app.database.database import get_db  
from sqlalchemy import text

router = APIRouter(
    prefix="/api/movimientos",
    tags=["Movimientos"],
    dependencies=[Depends(require_roles("admin", "bodeguero"))]
)

class MovimientoCreate(BaseModel):
    id_lote: int          
    cantidad_retirada: int
    destino: str
    encargado: str

@router.post("/", status_code=status.HTTP_201_CREATED)
def registrar_salida(movimiento: MovimientoCreate, connection = Depends(get_db)):
    try:
        # 1. Verificar si el lote existe por su id_lote y obtener el stock actual
        sql_lote = text("SELECT cantidad_actual, codigo_lote FROM lotes WHERE id_lote = :id_lote")
        result_lote = connection.execute(sql_lote, {"id_lote": movimiento.id_lote}).fetchone()
        
        if not result_lote:
            raise HTTPException(status_code=404, detail="El lote especificado no existe.")
        
        # Uso correcto de ._mapping para SQLAlchemy 2.0
        cantidad_actual = result_lote._mapping["cantidad_actual"]
        codigo_lote = result_lote._mapping["codigo_lote"]
        
        # 2. Validar que no se intente retirar más de lo que hay en bodega
        if cantidad_actual < movimiento.cantidad_retirada:
            raise HTTPException(
                status_code=400, 
                detail=f"Stock insuficiente en el lote {codigo_lote}. Solo quedan {cantidad_actual} unidades."
            )
        
        # 3. Restar el stock del lote físico correspondiente
        nueva_cantidad = cantidad_actual - movimiento.cantidad_retirada
        sql_update_lote = text("""
            UPDATE lotes 
            SET cantidad_actual = :nueva_cantidad 
            WHERE id_lote = :id_lote
        """)
        connection.execute(sql_update_lote, {
            "nueva_cantidad": nueva_cantidad,
            "id_lote": movimiento.id_lote
        })
        
        # 4. Registrar la salida en la nueva tabla de movimientos
        sql_insert_movimiento = text("""
            INSERT INTO movimientos (id_lote, cantidad_retirada, destino, encargado)
            VALUES (:id_lote, :cantidad_retirada, :destino, :encargado)
        """)
        connection.execute(sql_insert_movimiento, {
            "id_lote": movimiento.id_lote,
            "cantidad_retirada": movimiento.cantidad_retirada,
            "destino": movimiento.destino,
            "encargado": movimiento.encargado
        })
        
        # Guardar todos los cambios de manera atómica si todo anduvo bien
        connection.commit()
        return {"message": f"Salida del lote {codigo_lote} registrada exitosamente."}
        
    except HTTPException as http_exc:
        # Si salta un error de stock o un 404, limpiamos la transacción antes de responderle al Front
        connection.rollback()
        raise http_exc
    except Exception as e:
        # Si explota algo inesperado a nivel de sintaxis SQL o conexión
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Error inesperado en la base de datos: {str(e)}")

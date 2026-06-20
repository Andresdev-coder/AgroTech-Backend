from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta

# Importamos la conexión y los modelos reales
from app.database.database import get_db
from app.models import models
from app.schemas.schemas import InsumoCreate, InsumoResponse

router = APIRouter(
    prefix="/api/insumos",
    tags=["Insumos"]
)

@router.get("/", response_model=List[InsumoResponse])
def obtener_insumos(db: Session = Depends(get_db)):
    # Consultamos todos los productos de la base de datos MySQL
    productos = db.query(models.Producto).all()
    
    respuesta = []
    for p in productos:
        # Sumamos dinámicamente las existencias de todos sus lotes asociados
        stock_total = sum(lote.cantidad_actual for lote in p.lotes)
        
        # Lógica profesional de semaforización basada en tu stock_minimo (asumimos 50 para el ejemplo)
        stock_minimo_ejemplo = 50.0
        if stock_total > stock_minimo_ejemplo:
            estado = "Seguro"
        elif stock_total > 0:
            estado = "Alerta"
        else:
            estado = "Crítico"
        
        respuesta.append({
            "id": p.id_producto,
            "nombre": p.nombre_insumo,
            "categoria": p.categoria,
            "unidad_medida": "kg",  # Valor estándar por defecto o puedes mapearlo
            "stock_minimo": stock_minimo_ejemplo,
            "stock_actual": float(stock_total),
            "estado": estado,
            "fecha_creacion": datetime.now()  # Registra el momento de la consulta o creación
        })
    return respuesta


@router.post("/", response_model=InsumoResponse, status_code=status.HTTP_201_CREATED)
def crear_insumo(insumo: InsumoCreate, db: Session = Depends(get_db)):
    # 1. Creamos la entidad general del producto
    nuevo_producto = models.Producto(
        nombre_insumo=insumo.nombre,
        categoria=insumo.categoria
    )
    db.add(nuevo_producto)
    db.commit()  # Confirmamos para generar el id_producto autoincremental
    db.refresh(nuevo_producto)

    # 2. Como tu BD exige un lote para tener stock, le creamos automáticamente 
    # su lote inicial con cantidad 0 para cumplir con el esquema relacional.
    nuevo_lote_inicial = models.Lote(
        codigo_lote=f"LOT-{nuevo_producto.id_producto}-INIT",
        cantidad_inicial=1,  # Cumple con el CHECK > 0 de tu SQL
        cantidad_actual=0,   # Inicializa el stock en cero limpio
        fecha_vencimiento=date.today() + timedelta(days=365),  # 1 año de vigencia por defecto
        id_producto=nuevo_producto.id_producto
    )
    db.add(nuevo_lote_inicial)
    db.commit()

    # 3. Retornamos la estructura que el frontend y el InsumoResponse esperan
    return {
        "id": nuevo_producto.id_producto,
        "nombre": nuevo_producto.nombre_insumo,
        "categoria": nuevo_producto.categoria,
        "unidad_medida": insumo.unidad_medida,
        "stock_minimo": insumo.stock_minimo,
        "stock_actual": 0.0,
        "estado": "Crítico",  # Al crearse con 0 de stock arranca en Crítico
        "fecha_creacion": datetime.now()
    }
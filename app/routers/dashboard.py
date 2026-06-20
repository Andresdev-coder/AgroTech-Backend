from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

# Importamos la conexión, los modelos y el esquema de validación
from app.database.database import get_db
from app.models import models
from app.schemas.schemas import DashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("", response_model=DashboardResponse)
async def get_dashboard_data(db: Session = Depends(get_db)):
    """
    Consolida toda la información requerida por el Dashboard de AgroTech
    consultando directamente la base de datos MySQL.
    """
    
    # 1. KPI: Total Productos / Insumos registrados
    total_insumos = db.query(func.count(models.Producto.id_producto)).scalar() or 0

    # 2. KPI: Stock Total (Suma de la cantidad_actual de todos los lotes)
    stock_total = db.query(func.sum(models.Lote.cantidad_actual)).scalar() or 0

    # 3. KPI: Lotes Críticos (Lotes cuya fecha de vencimiento ya pasó o que tienen stock 0)
    hoy = datetime.now().date()
    lotes_criticos_count = db.query(func.count(models.Lote.id_lote)).filter(
        (models.Lote.fecha_vencimiento <= hoy) | (models.Lote.cantidad_actual == 0)
    ).scalar() or 0

    # 4. KPI: Simulación de Ventas del Mes
    ventas_mes = "$ 4,250,000"

    kpis_real = [
        {"title": "Total Insumos", "value": str(total_insumos), "subtitle": "Tipos registrados", "trend": "+12.5%", "isPositive": True, "trendText": "vs mes anterior", "icon": "Boxes", "iconBg": "bg-emerald-50 text-emerald-600"},
        {"title": "Stock Total", "value": f"{stock_total:,}", "subtitle": "Unidades disponibles", "trend": "+8.3%", "isPositive": True, "trendText": "vs mes anterior", "icon": "Layers", "iconBg": "bg-amber-50 text-amber-600"},
        {"title": "Lotes Críticos", "value": str(lotes_criticos_count), "subtitle": "Requieren atención", "trend": "Alerta", "isPositive": False, "trendText": "Revisar fechas/stock", "icon": "AlertTriangle", "iconBg": "bg-red-50 text-red-600"},
        {"title": "Ventas del Mes", "value": ventas_mes, "subtitle": "Total facturado", "trend": "+15.7%", "isPositive": True, "trendText": "vs mes anterior", "icon": "DollarSign", "iconBg": "bg-blue-50 text-blue-600"}
    ]

    # Datos de Clima (Estáticos)
    clima_mock = {
        "temperatura": "28°C",
        "condicion": "Parcialmente nublado",
        "humedad": "65%",
        "viento": "12 km/h",
        "presion": "1013 hPa"
    }

    # 5. CÁLCULO REAL PARA LA DONA DE ESTADOS (Semaforización)
    todos_los_lotes = db.query(models.Lote).all()
    verdes = 0
    amarillos = 0
    rojos = 0

    for lote in todos_los_lotes:
        dias_para_vencer = (lote.fecha_vencimiento - hoy).days
        
        # Reglas de negocio profesionales para AgroTech
        if dias_para_vencer <= 0 or lote.cantidad_actual == 0:
            rojos += 1       # Crítico: Vencido o sin existencias
        elif dias_para_vencer <= 30:
            amarillos += 1   # Alerta: Próximo a vencer (menos de 30 días)
        else:
            verdes += 1      # Seguro: Más de 30 días de vigencia y con stock

    total_lotes_bd = verdes + amarillos + rojos

    # 6. Lista de Lotes Críticos Dinámica
    lotes_db = db.query(models.Lote).filter(
        (models.Lote.fecha_vencimiento <= hoy) | (models.Lote.cantidad_actual == 0)
    ).limit(5).all()

    lotes_real = []
    for lote in lotes_db:
        es_vencido = lote.fecha_vencimiento <= hoy
        estado_texto = "Vencido" if es_vencido else "Sin Stock"
        badge_style = "bg-red-50 text-red-600" if es_vencido else "bg-amber-50 text-amber-600"

        lotes_real.append({
            "id": f"Lote: {lote.codigo_lote}",
            "nombre": lote.producto.nombre_insumo,
            "fecha": f"Vence: {lote.fecha_vencimiento.strftime('%d/%m/%Y')}",
            "estado": estado_texto,
            "badgeStyle": badge_style
        })

    # 7. Movimientos Recientes (FIFO)
    movimientos_db = db.query(models.Lote).order_by(models.Lote.fecha_ingreso.desc()).limit(5).all()
    
    movimientos_real = []
    for mov in movimientos_db:
        movimientos_real.append({
            "tipo": "Ingreso",
            "producto": mov.producto.nombre_insumo,
            "lote": mov.codigo_lote,
            "cantidad": f"+{mov.cantidad_inicial}",
            "usuario": "Sistema",
            "fecha": mov.fecha_ingreso.strftime("%d/%m/%Y %H:%M")
        })

    # Enviamos todo consolidado al Frontend, incluyendo el nuevo estado_lotes
    return {
        "kpis": kpis_real,
        "clima": clima_mock,
        "lotes_criticos": lotes_real,
        "movimientos": movimientos_real,
        "estado_lotes": {
            "total": total_lotes_bd,
            "verde": verdes,
            "amarillo": amarillos,
            "rojo": rojos
        }
    }
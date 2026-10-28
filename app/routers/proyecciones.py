from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.database import get_db

router = APIRouter(
    prefix="/api/proyecciones",
    tags=["Proyecciones"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("")
def obtener_proyecciones(db: Session = Depends(get_db)):
    hoy = date.today()
    inicio_30_dias = hoy - timedelta(days=29)
    inicio_90_dias = hoy - timedelta(days=89)
    fin_periodo = hoy + timedelta(days=1)

    stock_query = text(
        """
        SELECT
            p.id_producto,
            p.nombre_insumo AS producto,
            p.categoria,
            COALESCE(SUM(l.cantidad_actual), 0) AS stock_actual
        FROM productos p
        LEFT JOIN lotes l ON l.id_producto = p.id_producto
        GROUP BY p.id_producto, p.nombre_insumo, p.categoria
        ORDER BY p.nombre_insumo
        """
    )

    ventas_query = text(
        """
        SELECT
            p.id_producto,
            COALESCE(SUM(CASE
                WHEN v.fecha_venta >= :inicio_30 AND v.fecha_venta < :fin_periodo
                THEN d.cantidad ELSE 0 END), 0) AS vendido_30,
            COALESCE(SUM(CASE
                WHEN v.fecha_venta >= :inicio_90 AND v.fecha_venta < :fin_periodo
                THEN d.cantidad ELSE 0 END), 0) AS vendido_90,
            COALESCE(SUM(CASE
                WHEN v.fecha_venta >= :inicio_90 AND v.fecha_venta < :inicio_30
                THEN d.cantidad ELSE 0 END), 0) AS vendido_periodo_anterior,
            COUNT(DISTINCT CASE
                WHEN v.fecha_venta >= :inicio_30 AND v.fecha_venta < :fin_periodo
                THEN DATE(v.fecha_venta) END) AS dias_venta_30,
            COUNT(DISTINCT CASE
                WHEN v.fecha_venta >= :inicio_90 AND v.fecha_venta < :fin_periodo
                THEN DATE(v.fecha_venta) END) AS dias_venta_90
        FROM productos p
        LEFT JOIN lotes l ON l.id_producto = p.id_producto
        LEFT JOIN detalle_ventas d ON d.id_lote = l.id_lote
        LEFT JOIN ventas v ON v.id_venta = d.id_venta
        GROUP BY p.id_producto
        """
    )

    stock_rows = db.execute(stock_query).fetchall()
    ventas_rows = db.execute(
        ventas_query,
        {
            "inicio_30": inicio_30_dias,
            "inicio_90": inicio_90_dias,
            "fin_periodo": fin_periodo,
        },
    ).fetchall()
    ventas_map = {row._mapping["id_producto"]: row._mapping for row in ventas_rows}

    proyecciones = []
    total_stock = 0.0
    total_estimado_30 = 0.0
    productos_riesgo = 0

    for row in stock_rows:
        item = row._mapping
        id_producto = item["id_producto"]
        ventas = ventas_map.get(id_producto, {})
        producto = item["producto"]
        categoria = item["categoria"]
        stock_actual = round(float(item["stock_actual"] or 0), 2)
        vendido_30 = round(float(ventas.get("vendido_30", 0) or 0), 2)
        vendido_90 = round(float(ventas.get("vendido_90", 0) or 0), 2)
        vendido_periodo_anterior = round(float(ventas.get("vendido_periodo_anterior", 0) or 0), 2)
        dias_venta_30 = int(ventas.get("dias_venta_30", 0) or 0)
        dias_venta_90 = int(ventas.get("dias_venta_90", 0) or 0)

        promedio_diario_30 = vendido_30 / 30
        promedio_diario_periodo_anterior = vendido_periodo_anterior / 60
        # Da mayor peso al comportamiento reciente sin ignorar el nivel de ventas
        # de los dos meses anteriores. Los días sin ventas permanecen en el promedio.
        promedio_diario = (promedio_diario_30 * 0.65) + (promedio_diario_periodo_anterior * 0.35)
        proyeccion_30 = round(promedio_diario * 30, 2)
        proyeccion_90 = round(promedio_diario * 90, 2)
        dias_cobertura = round(stock_actual / promedio_diario, 1) if promedio_diario > 0 else None

        if dias_venta_90 == 0:
            calidad_historial = "Sin historial"
        elif dias_venta_90 >= 12 and dias_venta_30 >= 4:
            calidad_historial = "Suficiente"
        elif dias_venta_90 >= 5:
            calidad_historial = "Parcial"
        else:
            calidad_historial = "Limitado"

        if stock_actual <= 0:
            estado = "Crítico"
        elif dias_cobertura is None:
            estado = "Sin historial"
        elif dias_cobertura <= 30:
            estado = "Alerta"
        elif dias_cobertura <= 60:
            estado = "Moderado"
        else:
            estado = "Seguro"

        if estado in {"Crítico", "Alerta"}:
            productos_riesgo += 1

        total_stock += stock_actual
        total_estimado_30 += proyeccion_30

        proyecciones.append(
            {
                "id_producto": id_producto,
                "producto": producto,
                "categoria": categoria,
                "stock_actual": stock_actual,
                "vendido_30_dias": vendido_30,
                "vendido_90_dias": vendido_90,
                "dias_con_ventas_30": dias_venta_30,
                "dias_con_ventas_90": dias_venta_90,
                "promedio_diario": round(promedio_diario, 4),
                "proyeccion_30_dias": proyeccion_30,
                "proyeccion_90_dias": proyeccion_90,
                "dias_cobertura": dias_cobertura,
                "calidad_historial": calidad_historial,
                "estado": estado,
            }
        )

    proyecciones.sort(
        key=lambda item: (
            0 if item["estado"] == "Crítico" else 1 if item["estado"] == "Alerta" else 2,
            item["dias_cobertura"] if item["dias_cobertura"] is not None else 9999,
        )
    )

    return {
        "resumen": {
            "productos_evaluados": len(proyecciones),
            "stock_total": round(total_stock, 2),
            "demanda_estimada_30_dias": round(total_estimado_30, 2),
            "productos_en_riesgo": productos_riesgo,
        },
        "proyecciones": proyecciones,
    }

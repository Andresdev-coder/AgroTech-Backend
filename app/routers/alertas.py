from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_roles
from app.database.database import get_db
from app.models import models

router = APIRouter(
    prefix="/api/alertas",
    tags=["Alertas"],
    dependencies=[Depends(require_roles("admin", "bodeguero"))],
)


@router.get("")
def obtener_alertas(db: Session = Depends(get_db)):
    hoy = date.today()

    lotes = (
        db.query(
            models.Lote.id_lote,
            models.Lote.codigo_lote,
            models.Lote.cantidad_inicial,
            models.Lote.cantidad_actual,
            models.Lote.fecha_vencimiento,
            models.Producto.nombre_insumo,
            models.Producto.categoria,
        )
        .join(models.Producto, models.Producto.id_producto == models.Lote.id_producto)
        .all()
    )

    alertas = []
    for lote in lotes:
        dias_para_vencer = (lote.fecha_vencimiento - hoy).days
        stock = int(lote.cantidad_actual or 0)

        if stock == 0:
            tipo = "sin_stock"
            severidad = "critica"
            mensaje = "El lote quedo sin unidades disponibles."
        elif dias_para_vencer <= 0:
            tipo = "vencido"
            severidad = "critica"
            mensaje = "El lote ya vencio y requiere revision inmediata."
        elif dias_para_vencer <= 30:
            tipo = "por_vencer"
            severidad = "alta"
            mensaje = "El lote esta proximo a vencer."
        elif stock <= 10:
            tipo = "bajo_stock"
            severidad = "media"
            mensaje = "El lote tiene stock bajo."
        else:
            continue

        alertas.append(
            {
                "id_lote": lote.id_lote,
                "codigo_lote": lote.codigo_lote,
                "producto": lote.nombre_insumo,
                "categoria": lote.categoria,
                "cantidad_actual": stock,
                "cantidad_inicial": int(lote.cantidad_inicial or 0),
                "fecha_vencimiento": lote.fecha_vencimiento.isoformat(),
                "dias_para_vencer": dias_para_vencer,
                "tipo": tipo,
                "severidad": severidad,
                "mensaje": mensaje,
            }
        )

    alertas.sort(
        key=lambda item: (
            0 if item["severidad"] == "critica" else 1 if item["severidad"] == "alta" else 2,
            item["dias_para_vencer"],
        )
    )

    resumen = {
        "total": len(alertas),
        "criticas": sum(1 for item in alertas if item["severidad"] == "critica"),
        "altas": sum(1 for item in alertas if item["severidad"] == "alta"),
        "medias": sum(1 for item in alertas if item["severidad"] == "media"),
        "sin_stock": sum(1 for item in alertas if item["tipo"] == "sin_stock"),
        "vencidos": sum(1 for item in alertas if item["tipo"] == "vencido"),
    }

    return {"resumen": resumen, "alertas": alertas}

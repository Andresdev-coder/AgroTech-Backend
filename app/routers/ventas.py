from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database.database import get_db
from app.schemas.schemas import (
    VentaCreate,
    VentaFacturaCreate,
    VentaFacturaResponse,
    VentaResponse,
)

router = APIRouter(
    prefix="/api/ventas",
    tags=["Ventas"],
    dependencies=[Depends(require_roles("admin", "ventas"))],
)


def _normalizar_factura_meta(factura: dict | None) -> dict:
    factura = factura or {}
    return {
        "cliente_nombre": factura.get("cliente_nombre"),
        "cliente_nit": factura.get("cliente_nit"),
        "descuento_porcentaje": float(factura.get("descuento_porcentaje") or 0),
        "iva_porcentaje": float(factura.get("iva_porcentaje") or 19),
    }


@router.get("/", response_model=list[VentaResponse])
def listar_ventas(connection: Session = Depends(get_db)):
    sql = text(
        """
        SELECT
            v.id_venta,
            DATE_FORMAT(v.fecha_venta, '%d/%m/%Y %H:%i') AS fecha_venta,
            u.nombre AS vendedor,
            p.nombre_insumo AS producto,
            l.codigo_lote AS lote,
            d.cantidad,
            d.precio_unitario,
            (d.cantidad * d.precio_unitario) AS subtotal,
            l.cantidad_actual AS stock_restante
        FROM ventas v
        INNER JOIN usuarios u ON u.id_usuario = v.id_usuario
        INNER JOIN detalle_ventas d ON d.id_venta = v.id_venta
        INNER JOIN lotes l ON l.id_lote = d.id_lote
        INNER JOIN productos p ON p.id_producto = l.id_producto
        ORDER BY v.fecha_venta DESC, v.id_venta DESC, d.id_detalle DESC
        LIMIT 20
        """
    )

    resultado = connection.execute(sql)
    return [dict(row._mapping) for row in resultado.fetchall()]


def _registrar_venta_base(
    connection: Session,
    current_user: dict,
    items: list[dict],
    factura_meta: dict | None = None,
):
    if not items:
        raise HTTPException(
            status_code=400,
            detail="Debes agregar al menos un producto a la factura.",
        )

    meta = _normalizar_factura_meta(factura_meta)
    id_usuario = int(current_user["sub"])

    insert_venta = text(
        """
        INSERT INTO ventas (
            id_usuario,
            cliente_nombre,
            cliente_nit,
            subtotal_factura,
            descuento_porcentaje,
            descuento_valor,
            iva_porcentaje,
            iva_valor,
            total_factura
        )
        VALUES (
            :id_usuario,
            :cliente_nombre,
            :cliente_nit,
            0,
            :descuento_porcentaje,
            0,
            :iva_porcentaje,
            0,
            0
        )
        """
    )
    result_venta = connection.execute(
        insert_venta,
        {
            "id_usuario": id_usuario,
            "cliente_nombre": meta["cliente_nombre"],
            "cliente_nit": meta["cliente_nit"],
            "descuento_porcentaje": meta["descuento_porcentaje"],
            "iva_porcentaje": meta["iva_porcentaje"],
        },
    )
    id_venta = result_venta.lastrowid

    lote_query = text(
        """
        SELECT l.id_lote, l.codigo_lote, l.cantidad_actual, p.nombre_insumo
        FROM lotes l
        INNER JOIN productos p ON p.id_producto = l.id_producto
        WHERE l.id_lote = :id_lote
        """
    )

    insert_detalle = text(
        """
        INSERT INTO detalle_ventas (cantidad, precio_unitario, id_venta, id_lote)
        VALUES (:cantidad, :precio_unitario, :id_venta, :id_lote)
        """
    )

    update_lote = text(
        """
        UPDATE lotes
        SET cantidad_actual = :cantidad_actual
        WHERE id_lote = :id_lote
        """
    )

    subtotal_factura = 0.0

    for item in items:
        lote = connection.execute(lote_query, {"id_lote": item["id_lote"]}).fetchone()

        if not lote:
            raise HTTPException(
                status_code=404,
                detail=f"El lote con ID {item['id_lote']} no existe.",
            )

        lote_data = lote._mapping
        cantidad_actual = int(lote_data["cantidad_actual"])
        cantidad = int(item["cantidad"])
        precio_unitario = float(item["precio_unitario"])

        if cantidad > cantidad_actual:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente en el lote {lote_data['codigo_lote']}. Solo quedan {cantidad_actual} unidades.",
            )

        nuevo_stock = cantidad_actual - cantidad
        subtotal = round(cantidad * precio_unitario, 2)
        subtotal_factura = round(subtotal_factura + subtotal, 2)

        connection.execute(
            insert_detalle,
            {
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "id_venta": id_venta,
                "id_lote": item["id_lote"],
            },
        )

        connection.execute(
            update_lote,
            {
                "cantidad_actual": nuevo_stock,
                "id_lote": item["id_lote"],
            },
        )

    return id_venta, subtotal_factura


def _actualizar_resumen_factura(
    connection: Session,
    id_venta: int,
    subtotal_factura: float,
    descuento_porcentaje: float,
    iva_porcentaje: float,
):
    descuento_valor = round(subtotal_factura * (float(descuento_porcentaje) / 100.0), 2)
    base_gravable = round(max(0.0, subtotal_factura - descuento_valor), 2)
    iva_valor = round(base_gravable * (float(iva_porcentaje) / 100.0), 2)
    total_factura = round(base_gravable + iva_valor, 2)

    update_venta = text(
        """
        UPDATE ventas
        SET subtotal_factura = :subtotal_factura,
            descuento_porcentaje = :descuento_porcentaje,
            descuento_valor = :descuento_valor,
            iva_porcentaje = :iva_porcentaje,
            iva_valor = :iva_valor,
            total_factura = :total_factura
        WHERE id_venta = :id_venta
        """
    )

    connection.execute(
        update_venta,
        {
            "subtotal_factura": subtotal_factura,
            "descuento_porcentaje": float(descuento_porcentaje),
            "descuento_valor": descuento_valor,
            "iva_porcentaje": float(iva_porcentaje),
            "iva_valor": iva_valor,
            "total_factura": total_factura,
            "id_venta": id_venta,
        },
    )

    return descuento_valor, iva_valor, total_factura


def _obtener_venta_completa(connection: Session, id_venta: int):
    sql = text(
        """
        SELECT
            v.id_venta,
            DATE_FORMAT(v.fecha_venta, '%d/%m/%Y %H:%i') AS fecha_venta,
            u.nombre AS vendedor,
            v.cliente_nombre,
            v.cliente_nit,
            v.subtotal_factura,
            v.descuento_porcentaje,
            v.descuento_valor,
            v.iva_porcentaje,
            v.iva_valor,
            v.total_factura,
            p.nombre_insumo AS producto,
            l.codigo_lote AS lote,
            d.cantidad,
            d.precio_unitario,
            (d.cantidad * d.precio_unitario) AS subtotal,
            l.cantidad_actual AS stock_restante
        FROM ventas v
        INNER JOIN usuarios u ON u.id_usuario = v.id_usuario
        INNER JOIN detalle_ventas d ON d.id_venta = v.id_venta
        INNER JOIN lotes l ON l.id_lote = d.id_lote
        INNER JOIN productos p ON p.id_producto = l.id_producto
        WHERE v.id_venta = :id_venta
        ORDER BY d.id_detalle ASC
        """
    )

    resultado = connection.execute(sql, {"id_venta": id_venta})
    items = [dict(row._mapping) for row in resultado.fetchall()]
    first = items[0] if items else {}

    subtotal_factura = float(first.get("subtotal_factura") or 0)
    descuento_porcentaje = float(first.get("descuento_porcentaje") or 0)
    descuento_valor = float(first.get("descuento_valor") or 0)
    iva_porcentaje = float(first.get("iva_porcentaje") or 0)
    iva_valor = float(first.get("iva_valor") or 0)
    total_factura = float(first.get("total_factura") or 0)

    if not total_factura:
        total_factura = round(max(0.0, subtotal_factura - descuento_valor) + iva_valor, 2)

    return {
        "vendedor": first.get("vendedor", "Sistema"),
        "fecha_venta": first.get("fecha_venta", ""),
        "cliente_nombre": first.get("cliente_nombre"),
        "cliente_nit": first.get("cliente_nit"),
        "subtotal_factura": subtotal_factura,
        "descuento_porcentaje": descuento_porcentaje,
        "descuento_valor": descuento_valor,
        "iva_porcentaje": iva_porcentaje,
        "iva_valor": iva_valor,
        "total_factura": total_factura,
        "items": items,
        "consecutivo": f"FAC-{id_venta:05d}",
    }


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=VentaFacturaResponse)
def registrar_venta(
    venta: VentaCreate,
    current_user: dict = Depends(get_current_user),
    connection: Session = Depends(get_db),
):
    try:
        id_venta, subtotal_factura = _registrar_venta_base(
            connection,
            current_user,
            [
                {
                    "id_lote": venta.id_lote,
                    "cantidad": venta.cantidad,
                    "precio_unitario": venta.precio_unitario,
                }
            ],
            {
                "descuento_porcentaje": 0,
                "iva_porcentaje": 19,
            },
        )

        _actualizar_resumen_factura(connection, id_venta, subtotal_factura, 0, 19)
        connection.commit()
        factura = _obtener_venta_completa(connection, id_venta)

        return {
            "message": "Venta registrada exitosamente.",
            "id_venta": id_venta,
            "consecutivo": factura["consecutivo"],
            "vendedor": factura["vendedor"],
            "fecha_venta": factura["fecha_venta"],
            "cliente_nombre": factura["cliente_nombre"],
            "cliente_nit": factura["cliente_nit"],
            "subtotal_factura": factura["subtotal_factura"],
            "descuento_porcentaje": factura["descuento_porcentaje"],
            "descuento_valor": factura["descuento_valor"],
            "iva_porcentaje": factura["iva_porcentaje"],
            "iva_valor": factura["iva_valor"],
            "total_factura": factura["total_factura"],
            "items": factura["items"],
        }
    except HTTPException as http_exc:
        connection.rollback()
        raise http_exc
    except Exception as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar la venta: {str(e)}",
        )


@router.post("/factura", status_code=status.HTTP_201_CREATED, response_model=VentaFacturaResponse)
def registrar_factura(
    factura: VentaFacturaCreate,
    current_user: dict = Depends(get_current_user),
    connection: Session = Depends(get_db),
):
    try:
        items = [
            {
                "id_lote": item.id_lote,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
            }
            for item in factura.items
        ]

        id_venta, subtotal_factura = _registrar_venta_base(
            connection,
            current_user,
            items,
            {
                "cliente_nombre": factura.cliente_nombre,
                "cliente_nit": factura.cliente_nit,
                "descuento_porcentaje": factura.descuento_porcentaje,
                "iva_porcentaje": factura.iva_porcentaje,
            },
        )

        _actualizar_resumen_factura(
            connection,
            id_venta,
            subtotal_factura,
            factura.descuento_porcentaje,
            factura.iva_porcentaje,
        )

        connection.commit()
        factura_completa = _obtener_venta_completa(connection, id_venta)

        return {
            "message": "Factura registrada exitosamente.",
            "id_venta": id_venta,
            "consecutivo": factura_completa["consecutivo"],
            "vendedor": factura_completa["vendedor"],
            "fecha_venta": factura_completa["fecha_venta"],
            "cliente_nombre": factura_completa["cliente_nombre"],
            "cliente_nit": factura_completa["cliente_nit"],
            "subtotal_factura": factura_completa["subtotal_factura"],
            "descuento_porcentaje": factura_completa["descuento_porcentaje"],
            "descuento_valor": factura_completa["descuento_valor"],
            "iva_porcentaje": factura_completa["iva_porcentaje"],
            "iva_valor": factura_completa["iva_valor"],
            "total_factura": factura_completa["total_factura"],
            "items": factura_completa["items"],
        }
    except HTTPException as http_exc:
        connection.rollback()
        raise http_exc
    except Exception as e:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar la factura: {str(e)}",
        )

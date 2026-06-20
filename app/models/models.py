from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.database import Base

class Rol(Base):
    __tablename__ = "roles"

    id_rol = Column(Integer, primary_key=True, autoincrement=True)
    nombre_rol = Column(String(30), nullable=False, unique=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(100), nullable=False, unique=True)
    contrasena = Column(String(255), nullable=False)
    id_rol = Column(Integer, ForeignKey("roles.id_rol", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)


class Producto(Base):
    __tablename__ = "productos"

    id_producto = Column(Integer, primary_key=True, autoincrement=True)
    nombre_insumo = Column(String(100), nullable=False)
    categoria = Column(String(50), nullable=False)

    # Relación uno a muchos con lotes
    lotes = relationship("Lote", back_populates="producto")


class Lote(Base):
    __tablename__ = "lotes"

    id_lote = Column(Integer, primary_key=True, autoincrement=True)
    codigo_lote = Column(String(50), nullable=False, unique=True)
    cantidad_inicial = Column(Integer, nullable=False)
    cantidad_actual = Column(Integer, nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    fecha_ingreso = Column(DateTime, server_default=func.now())
    id_producto = Column(Integer, ForeignKey("productos.id_producto", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)

    # Relación inversa hacia producto
    producto = relationship("Producto", back_populates="lotes")
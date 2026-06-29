-- =================================================================
-- SCRIPT DE CREACIÓN DE LA BASE DE DATOS: AGROTECH
-- Autor: Andres
-- Motor: MySQL 8.0+
-- =================================================================

-- 1. Crear la base de datos si no existe y asignar codificación UTF-8
CREATE DATABASE IF NOT EXISTS agrotech_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE agrotech_db;

-- =================================================================
-- MÓDULO 1: SEGURIDAD Y USUARIOS (RF-01, CU-01)
-- =================================================================

-- Crear tabla de Roles
CREATE TABLE roles (
    id_rol INT AUTO_INCREMENT,
    nombre_rol VARCHAR(30) NOT NULL UNIQUE,
    CONSTRAINT PK_roles PRIMARY KEY (id_rol)
) ENGINE=InnoDB;

-- Crear tabla de Usuarios
CREATE TABLE usuarios (
    id_usuario INT AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(100) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL, -- Espacio optimizado para hash bcrypt (RNF-01)
    id_rol INT NOT NULL,
    CONSTRAINT PK_usuarios PRIMARY KEY (id_usuario),
    CONSTRAINT FK_usuarios_roles FOREIGN KEY (id_rol) 
        REFERENCES roles(id_rol) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
select * from usuarios;
-- =================================================================
-- MÓDULO 2: INVENTARIO INTELIGENTE POR LOTES (RF-02, RF-03, CU-02)
-- =================================================================

-- Crear tabla de Productos (Información general)
CREATE TABLE productos (
    id_producto INT AUTO_INCREMENT,
    nombre_insumo VARCHAR(100) NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    CONSTRAINT PK_productos PRIMARY KEY (id_producto)
) ENGINE=InnoDB;

-- Crear tabla de Lotes (Corazón de la semaforización y FIFO)
CREATE TABLE lotes (
    id_lote INT AUTO_INCREMENT,
    codigo_lote VARCHAR(50) NOT NULL UNIQUE,
    cantidad_inicial INT NOT NULL,
    cantidad_actual INT NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_producto INT NOT NULL,
    CONSTRAINT PK_lotes PRIMARY KEY (id_lote),
    CONSTRAINT CK_cantidad_inicial CHECK (cantidad_inicial > 0),
    CONSTRAINT CK_cantidad_actual CHECK (cantidad_actual >= 0),
    CONSTRAINT FK_lotes_productos FOREIGN KEY (id_producto) 
        REFERENCES productos(id_producto) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =================================================================
-- MÓDULO 3: VENTAS Y DETALLE FIFO (RF-05, RF-06, CU-03)
-- =================================================================

-- Crear tabla de Ventas (Cabecera de factura)
CREATE TABLE ventas (
    id_venta INT AUTO_INCREMENT,
    fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    id_usuario INT NOT NULL,
    CONSTRAINT PK_ventas PRIMARY KEY (id_venta),
    CONSTRAINT FK_ventas_usuarios FOREIGN KEY (id_usuario) 
        REFERENCES usuarios(id_usuario) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Crear tabla de Detalle de Ventas (Renglones vinculados al lote físico)
CREATE TABLE detalle_ventas (
    id_detalle INT AUTO_INCREMENT,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    id_venta INT NOT NULL,
    id_lote INT NOT NULL,
    CONSTRAINT PK_detalle_ventas PRIMARY KEY (id_detalle),
    CONSTRAINT CK_cantidad_venta CHECK (cantidad > 0),
    CONSTRAINT CK_precio_positivo CHECK (precio_unitario >= 0),
    CONSTRAINT FK_detalle_ventas_ventas FOREIGN KEY (id_venta) 
        REFERENCES ventas(id_venta) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT FK_detalle_ventas_lotes FOREIGN KEY (id_lote) 
        REFERENCES lotes(id_lote) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Crear tabla de movimientos
CREATE TABLE movimientos (
    id_movimiento INT AUTO_INCREMENT,
    cantidad_retirada INT NOT NULL,
    fecha_movimiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    destino VARCHAR(100) NOT NULL,
    encargado VARCHAR(100) NOT NULL,
    id_lote INT NOT NULL,
    CONSTRAINT PK_movimientos PRIMARY KEY (id_movimiento),
    CONSTRAINT CK_cantidad_movimiento CHECK (cantidad_retirada > 0),
    CONSTRAINT FK_movimientos_lotes FOREIGN KEY (id_lote) 
        REFERENCES lotes(id_lote) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- =================================================================
-- INSERCIÓN DE DATOS DE PRUEBA (DATA SEEDING)
-- =================================================================

-- Insertar los roles base del sistema
INSERT INTO roles (nombre_rol) VALUES 
('Administrador'),
('Bodeguero'),
('Vendedor');

-- Insertar usuarios de prueba (Nota: En producción las contraseñas irán encriptadas)
INSERT INTO usuarios (nombre, correo, contrasena, id_rol) VALUES 
('Carlos Andrés', 'admin@agrotech.com', 'admin123', 1),
('Francisco Gómez', 'bodega@agrotech.com', 'bodega123', 2),
('Luisa Martínez', 'ventas@agrotech.com', 'ventas123', 3);

-- Insertar productos agrícolas base
INSERT INTO productos (nombre_insumo, categoria) VALUES 
('Fertilizante Urea de Nitrógeno', 'Fertilizantes'),
('Fungicida Mancozeb 80%', 'Plaguicidas'),
('Semilla de Maíz Híbrido', 'Semillas');

-- Insertar lotes con diferentes fechas para probar FIFO y semaforización
-- (Asumiendo que hoy es junio de 2026)
INSERT INTO lotes (codigo_lote, cantidad_inicial, cantidad_actual, fecha_vencimiento, id_producto) VALUES 
('LOT-UREA-01', 100, 45, '2026-07-15', 1), -- Lote próximo a vencer (Estado Rojo - Se debe vender primero)
('LOT-UREA-02', 150, 150, '2026-12-20', 1), -- Lote seguro (Estado Verde)
('LOT-FUNGI-01', 50, 12, '2026-08-01', 2);  -- Lote en alerta intermedia (Estado Amarillo)
-- Huancayoga
-- Migración 20260819_01: integridad del esquema y preparación para acceso social.
-- Requiere MySQL 8.0.16 o posterior por el uso de restricciones CHECK.
-- Los respaldos previos se crean fuera de esta migración para no duplicarlos
-- cuando el esquema se instale en un ambiente nuevo.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) NOT NULL,
    descripcion VARCHAR(255) NOT NULL,
    aplicada_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Normalización no destructiva antes de crear índices y restricciones.
UPDATE clientes
SET dni = TRIM(dni),
    celular = NULLIF(TRIM(celular), ''),
    correo = NULLIF(LOWER(TRIM(correo)), ''),
    estado = LOWER(TRIM(estado));

UPDATE productos SET estado = LOWER(TRIM(estado));
UPDATE servicios SET estado = LOWER(TRIM(estado));
UPDATE publicaciones
SET tipo = LOWER(TRIM(tipo)),
    estado = LOWER(TRIM(estado));
UPDATE reservas SET estado = LOWER(TRIM(estado));
UPDATE pedidos SET estado = LOWER(TRIM(estado));

-- Conserva los registros históricos y elimina únicamente referencias inválidas.
UPDATE reservas r
LEFT JOIN clientes c ON c.id = r.cliente_id
SET r.cliente_id = NULL
WHERE r.cliente_id IS NOT NULL
  AND c.id IS NULL;

UPDATE pedidos p
LEFT JOIN clientes c ON c.id = p.cliente_id
SET p.cliente_id = NULL
WHERE p.cliente_id IS NOT NULL
  AND c.id IS NULL;

-- Unifica el juego de caracteres y la colación de las tablas del sistema.
ALTER TABLE clientes CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE usuarios CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE servicios CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE productos CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE reservas CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE pedidos CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE publicaciones CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Clientes: correo verificable, consentimiento y seguimiento de acceso.
ALTER TABLE clientes
    MODIFY correo VARCHAR(254) NULL,
    MODIFY estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    ADD COLUMN correo_verificado_at DATETIME NULL AFTER correo,
    ADD COLUMN acepta_promociones TINYINT(1) NOT NULL DEFAULT 0 AFTER correo_verificado_at,
    ADD COLUMN acepta_promociones_at DATETIME NULL AFTER acepta_promociones,
    ADD COLUMN ultimo_acceso_at DATETIME NULL AFTER fecha_registro,
    ADD CONSTRAINT chk_clientes_dni
        CHECK (REGEXP_LIKE(dni, '^[0-9]{8}$')),
    ADD CONSTRAINT chk_clientes_celular
        CHECK (celular IS NULL OR REGEXP_LIKE(celular, '^9[0-9]{8}$')),
    ADD CONSTRAINT chk_clientes_estado
        CHECK (estado IN ('activo', 'inactivo', 'pendiente')),
    ADD CONSTRAINT chk_clientes_promociones
        CHECK (acepta_promociones IN (0, 1));

CREATE UNIQUE INDEX uq_clientes_correo ON clientes (correo);
CREATE UNIQUE INDEX uq_clientes_reset_token ON clientes (reset_token);
CREATE INDEX idx_clientes_estado_correo ON clientes (estado, correo);

-- Valores válidos y datos obligatorios según los formularios actuales.
ALTER TABLE productos
    MODIFY stock INT NOT NULL DEFAULT 0,
    MODIFY estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    ADD CONSTRAINT chk_productos_precio CHECK (precio >= 0),
    ADD CONSTRAINT chk_productos_stock CHECK (stock >= 0),
    ADD CONSTRAINT chk_productos_estado CHECK (estado IN ('activo', 'inactivo'));

ALTER TABLE servicios
    MODIFY precio DECIMAL(10,2) NOT NULL,
    MODIFY duracion_minutos INT NOT NULL,
    MODIFY estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    ADD CONSTRAINT chk_servicios_precio CHECK (precio >= 0),
    ADD CONSTRAINT chk_servicios_duracion CHECK (duracion_minutos > 0),
    ADD CONSTRAINT chk_servicios_estado CHECK (estado IN ('activo', 'inactivo'));

ALTER TABLE publicaciones
    MODIFY tipo VARCHAR(40) NOT NULL DEFAULT 'monologo',
    MODIFY estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    MODIFY fecha_publicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT chk_publicaciones_tipo
        CHECK (tipo IN ('monologo', 'frase', 'noticia', 'foto', 'promocion')),
    ADD CONSTRAINT chk_publicaciones_estado
        CHECK (estado IN ('activo', 'inactivo'));

-- Se retiran temporalmente las relaciones antiguas para poder endurecer
-- las columnas relacionadas. Se recrean más abajo con reglas explícitas.
ALTER TABLE reservas DROP FOREIGN KEY reservas_ibfk_1;
ALTER TABLE pedidos DROP FOREIGN KEY pedidos_ibfk_1;

ALTER TABLE reservas
    MODIFY servicio_id INT NOT NULL,
    MODIFY estado VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    ADD CONSTRAINT chk_reservas_estado
        CHECK (estado IN ('pendiente', 'confirmada', 'cancelada', 'atendida'));

ALTER TABLE pedidos
    MODIFY producto_id INT NOT NULL,
    MODIFY cantidad INT NOT NULL DEFAULT 1,
    MODIFY total DECIMAL(10,2) NOT NULL,
    MODIFY estado VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    ADD CONSTRAINT chk_pedidos_cantidad CHECK (cantidad > 0),
    ADD CONSTRAINT chk_pedidos_total CHECK (total >= 0),
    ADD CONSTRAINT chk_pedidos_estado
        CHECK (estado IN ('pendiente', 'pagado', 'entregado', 'cancelado'));

-- Índices alineados con las consultas de Flask.
CREATE INDEX idx_productos_estado_nombre ON productos (estado, nombre);
CREATE INDEX idx_servicios_estado_nombre ON servicios (estado, nombre);
CREATE INDEX idx_publicaciones_estado_fecha ON publicaciones (estado, fecha_publicacion);
CREATE INDEX idx_reservas_cliente_fecha_hora ON reservas (cliente_id, fecha, hora);
CREATE INDEX idx_reservas_estado_fecha_registro ON reservas (estado, fecha_registro);
CREATE INDEX idx_pedidos_cliente_fecha ON pedidos (cliente_id, fecha_pedido);
CREATE INDEX idx_pedidos_estado_fecha ON pedidos (estado, fecha_pedido);

-- Las reservas y pedidos históricos se conservan si un cliente se elimina.
ALTER TABLE reservas
    ADD CONSTRAINT fk_reservas_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE pedidos
    ADD CONSTRAINT fk_pedidos_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE reservas
    ADD CONSTRAINT fk_reservas_servicio
        FOREIGN KEY (servicio_id) REFERENCES servicios(id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE pedidos
    ADD CONSTRAINT fk_pedidos_producto
        FOREIGN KEY (producto_id) REFERENCES productos(id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

-- Una cuenta social pertenece a un cliente y se identifica por el ID estable
-- entregado por el proveedor. No se guardan access_token ni refresh_token.
CREATE TABLE IF NOT EXISTS cliente_cuentas_sociales (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    proveedor VARCHAR(20) NOT NULL,
    proveedor_usuario_id VARCHAR(255)
        CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    correo_proveedor VARCHAR(254) NULL,
    correo_proveedor_verificado TINYINT(1) NOT NULL DEFAULT 0,
    nombre_proveedor VARCHAR(150) NULL,
    avatar_url VARCHAR(500) NULL,
    vinculado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso_at DATETIME NULL,
    actualizado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_social_proveedor_usuario
        UNIQUE (proveedor, proveedor_usuario_id),
    CONSTRAINT uq_social_cliente_proveedor
        UNIQUE (cliente_id, proveedor),
    CONSTRAINT chk_social_proveedor
        CHECK (proveedor IN ('google', 'facebook', 'tiktok')),
    CONSTRAINT chk_social_correo_verificado
        CHECK (correo_proveedor_verificado IN (0, 1)),
    CONSTRAINT fk_social_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Códigos de correo de un solo uso. Solo se conserva el hash del código.
CREATE TABLE IF NOT EXISTS verificaciones_correo (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    correo VARCHAR(254) NOT NULL,
    codigo_hash VARCHAR(255)
        CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    proposito VARCHAR(30) NOT NULL DEFAULT 'registro',
    intentos TINYINT UNSIGNED NOT NULL DEFAULT 0,
    expira_at DATETIME NOT NULL,
    usado_at DATETIME NULL,
    creado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT chk_verificacion_proposito
        CHECK (proposito IN ('registro', 'vinculacion', 'cambio_correo', 'recuperacion')),
    CONSTRAINT chk_verificacion_intentos
        CHECK (intentos <= 10),
    CONSTRAINT fk_verificacion_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_verificacion_cliente_estado (cliente_id, usado_at, expira_at),
    INDEX idx_verificacion_correo_fecha (correo, creado_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO schema_migrations (version, descripcion)
VALUES (
    '20260819_01',
    'Integridad del esquema, relaciones con clientes y preparación para acceso social'
);

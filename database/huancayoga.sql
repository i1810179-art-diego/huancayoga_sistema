-- Huancayoga - esquema estructural de MySQL 8.4
-- Actualizado por la migración 20260819_04.
-- Este archivo no contiene clientes, correos, contraseñas ni datos de producción.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `schema_migrations` (
    `version` VARCHAR(100) NOT NULL,
    `descripcion` VARCHAR(255) NOT NULL,
    `aplicada_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `clientes` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `dni` VARCHAR(8) NOT NULL,
    `nombres` VARCHAR(100) NOT NULL,
    `apellido_paterno` VARCHAR(100) NULL,
    `apellido_materno` VARCHAR(100) NULL,
    `celular` VARCHAR(20) NULL,
    `correo` VARCHAR(254) NULL,
    `correo_verificado_at` DATETIME NULL,
    `acepta_promociones` TINYINT(1) NOT NULL DEFAULT 0,
    `acepta_promociones_at` DATETIME NULL,
    `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `ultimo_acceso_at` DATETIME NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'activo',
    `password_hash` VARCHAR(255) NULL,
    `reset_token` VARCHAR(255) NULL,
    `reset_token_expira` DATETIME NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_clientes_dni` (`dni`),
    UNIQUE KEY `uq_clientes_correo` (`correo`),
    UNIQUE KEY `uq_clientes_reset_token` (`reset_token`),
    KEY `idx_clientes_estado_correo` (`estado`, `correo`),
    CONSTRAINT `chk_clientes_dni`
        CHECK (REGEXP_LIKE(`dni`, '^[0-9]{8}$')),
    CONSTRAINT `chk_clientes_celular`
        CHECK (`celular` IS NULL OR REGEXP_LIKE(`celular`, '^9[0-9]{8}$')),
    CONSTRAINT `chk_clientes_estado`
        CHECK (`estado` IN ('activo', 'inactivo', 'pendiente')),
    CONSTRAINT `chk_clientes_promociones`
        CHECK (`acepta_promociones` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `usuarios` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `usuario` VARCHAR(50) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `rol` VARCHAR(30) NOT NULL DEFAULT 'admin',
    `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_usuarios_usuario` (`usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `servicios` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    `precio` DECIMAL(10,2) NOT NULL,
    `duracion_minutos` INT NOT NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'activo',
    PRIMARY KEY (`id`),
    KEY `idx_servicios_estado_nombre` (`estado`, `nombre`),
    CONSTRAINT `chk_servicios_precio` CHECK (`precio` >= 0),
    CONSTRAINT `chk_servicios_duracion` CHECK (`duracion_minutos` > 0),
    CONSTRAINT `chk_servicios_estado`
        CHECK (`estado` IN ('activo', 'inactivo'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `productos` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(100) NOT NULL,
    `descripcion` TEXT NULL,
    `precio` DECIMAL(10,2) NOT NULL,
    `stock` INT NOT NULL DEFAULT 0,
    `imagen` VARCHAR(255) NULL,
    `estado` VARCHAR(20) NOT NULL DEFAULT 'activo',
    `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_productos_estado_nombre` (`estado`, `nombre`),
    CONSTRAINT `chk_productos_precio` CHECK (`precio` >= 0),
    CONSTRAINT `chk_productos_stock` CHECK (`stock` >= 0),
    CONSTRAINT `chk_productos_estado`
        CHECK (`estado` IN ('activo', 'inactivo'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `publicaciones` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `titulo` VARCHAR(150) NOT NULL,
    `contenido` TEXT NOT NULL,
    `imagen` VARCHAR(255) NULL,
    `tipo` VARCHAR(40) NOT NULL DEFAULT 'monologo',
    `estado` VARCHAR(20) NOT NULL DEFAULT 'activo',
    `fecha_publicacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_publicaciones_estado_fecha` (`estado`, `fecha_publicacion`),
    CONSTRAINT `chk_publicaciones_tipo`
        CHECK (`tipo` IN ('monologo', 'frase', 'noticia', 'foto', 'promocion')),
    CONSTRAINT `chk_publicaciones_estado`
        CHECK (`estado` IN ('activo', 'inactivo'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `reservas` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `nombre_cliente` VARCHAR(100) NOT NULL,
    `celular` VARCHAR(20) NOT NULL,
    `correo` VARCHAR(100) NULL,
    `servicio_id` INT NOT NULL,
    `cantidad_personas` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    `fecha` DATE NOT NULL,
    `hora` TIME NOT NULL,
    `comentario` TEXT NULL,
    `estado` VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `cliente_id` INT NULL,
    `tipo_reserva` VARCHAR(20) NOT NULL DEFAULT 'regular',
    `duracion_minutos` SMALLINT UNSIGNED NOT NULL DEFAULT 60,
    `tipo_lugar` VARCHAR(20) NOT NULL DEFAULT 'local',
    `direccion_externa` VARCHAR(255) NULL,
    `horario_activo_fecha` DATE
        GENERATED ALWAYS AS (
            CASE
                WHEN `estado` IN ('pendiente', 'confirmada') THEN `fecha`
                ELSE NULL
            END
        ) STORED,
    `horario_activo_hora` TIME
        GENERATED ALWAYS AS (
            CASE
                WHEN `estado` IN ('pendiente', 'confirmada') THEN `hora`
                ELSE NULL
            END
        ) STORED,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_reservas_horario_activo`
        (`horario_activo_fecha`, `horario_activo_hora`),
    KEY `idx_reservas_servicio` (`servicio_id`),
    KEY `idx_reservas_cliente_fecha_hora` (`cliente_id`, `fecha`, `hora`),
    KEY `idx_reservas_estado_fecha_registro` (`estado`, `fecha_registro`),
    KEY `idx_reservas_agenda` (`fecha`, `hora`, `estado`),
    CONSTRAINT `fk_reservas_cliente`
        FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT `fk_reservas_servicio`
        FOREIGN KEY (`servicio_id`) REFERENCES `servicios` (`id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `chk_reservas_estado`
        CHECK (`estado` IN ('pendiente', 'confirmada', 'cancelada', 'atendida')),
    CONSTRAINT `chk_reservas_cantidad_personas`
        CHECK (`cantidad_personas` BETWEEN 1 AND 40),
    CONSTRAINT `chk_reservas_tipo`
        CHECK (`tipo_reserva` IN ('regular', 'institucional')),
    CONSTRAINT `chk_reservas_duracion`
        CHECK (`duracion_minutos` BETWEEN 15 AND 240),
    CONSTRAINT `chk_reservas_lugar`
        CHECK (`tipo_lugar` IN ('local', 'externo')),
    CONSTRAINT `chk_reservas_direccion`
        CHECK (
            `tipo_lugar` = 'local'
            OR (
                `direccion_externa` IS NOT NULL
                AND CHAR_LENGTH(TRIM(`direccion_externa`)) >= 5
            )
        ),
    CONSTRAINT `chk_reservas_mismo_dia`
        CHECK (TIME_TO_SEC(`hora`) + `duracion_minutos` * 60 <= 86400)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `reserva_programa_detalles` (
    `reserva_id` INT NOT NULL,
    `categoria` VARCHAR(40) NOT NULL,
    `nombre_organizacion` VARCHAR(150) NOT NULL,
    `rango_edad` VARCHAR(80) NULL,
    `necesidades_apoyo` TEXT NULL,
    `creado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `actualizado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`reserva_id`),
    KEY `idx_programa_categoria_organizacion`
        (`categoria`, `nombre_organizacion`),
    CONSTRAINT `fk_programa_reserva`
        FOREIGN KEY (`reserva_id`) REFERENCES `reservas` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT `chk_programa_categoria`
        CHECK (
            `categoria` IN (
                'colegio',
                'instituto',
                'universidad',
                'corporativo',
                'ninos',
                'adultos_mayores',
                'inclusivo_adaptado',
                'asociacion_familiar',
                'otro'
            )
        ),
    CONSTRAINT `chk_programa_organizacion`
        CHECK (CHAR_LENGTH(TRIM(`nombre_organizacion`)) >= 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `reserva_bloques_horario` (
    `fecha` DATE NOT NULL,
    `hora_bloque` TIME NOT NULL,
    `reserva_id` INT NOT NULL,
    PRIMARY KEY (`fecha`, `hora_bloque`),
    UNIQUE KEY `uq_bloque_reserva` (`reserva_id`, `hora_bloque`),
    CONSTRAINT `fk_bloque_reserva`
        FOREIGN KEY (`reserva_id`) REFERENCES `reservas` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `pedidos` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `nombre_cliente` VARCHAR(100) NOT NULL,
    `celular` VARCHAR(20) NOT NULL,
    `producto_id` INT NOT NULL,
    `cantidad` INT NOT NULL DEFAULT 1,
    `total` DECIMAL(10,2) NOT NULL,
    `estado` VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    `fecha_pedido` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `cliente_id` INT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_pedidos_producto` (`producto_id`),
    KEY `idx_pedidos_cliente_fecha` (`cliente_id`, `fecha_pedido`),
    KEY `idx_pedidos_estado_fecha` (`estado`, `fecha_pedido`),
    CONSTRAINT `fk_pedidos_cliente`
        FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT `fk_pedidos_producto`
        FOREIGN KEY (`producto_id`) REFERENCES `productos` (`id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `chk_pedidos_cantidad` CHECK (`cantidad` > 0),
    CONSTRAINT `chk_pedidos_total` CHECK (`total` >= 0),
    CONSTRAINT `chk_pedidos_estado`
        CHECK (`estado` IN ('pendiente', 'pagado', 'entregado', 'cancelado'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `cliente_cuentas_sociales` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `cliente_id` INT NOT NULL,
    `proveedor` VARCHAR(20) NOT NULL,
    `proveedor_usuario_id` VARCHAR(255)
        CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `correo_proveedor` VARCHAR(254) NULL,
    `correo_proveedor_verificado` TINYINT(1) NOT NULL DEFAULT 0,
    `nombre_proveedor` VARCHAR(150) NULL,
    `avatar_url` VARCHAR(500) NULL,
    `vinculado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `ultimo_acceso_at` DATETIME NULL,
    `actualizado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_social_proveedor_usuario`
        (`proveedor`, `proveedor_usuario_id`),
    UNIQUE KEY `uq_social_cliente_proveedor`
        (`cliente_id`, `proveedor`),
    CONSTRAINT `fk_social_cliente`
        FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT `chk_social_proveedor`
        CHECK (`proveedor` IN ('google', 'facebook', 'tiktok')),
    CONSTRAINT `chk_social_correo_verificado`
        CHECK (`correo_proveedor_verificado` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `verificaciones_correo` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `cliente_id` INT NOT NULL,
    `correo` VARCHAR(254) NOT NULL,
    `codigo_hash` VARCHAR(255)
        CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `proposito` VARCHAR(30) NOT NULL DEFAULT 'registro',
    `intentos` TINYINT UNSIGNED NOT NULL DEFAULT 0,
    `expira_at` DATETIME NOT NULL,
    `usado_at` DATETIME NULL,
    `creado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_verificacion_cliente_estado`
        (`cliente_id`, `usado_at`, `expira_at`),
    KEY `idx_verificacion_correo_fecha` (`correo`, `creado_at`),
    CONSTRAINT `fk_verificacion_cliente`
        FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT `chk_verificacion_proposito`
        CHECK (`proposito` IN ('registro', 'vinculacion', 'cambio_correo', 'recuperacion')),
    CONSTRAINT `chk_verificacion_intentos` CHECK (`intentos` <= 10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `integraciones_oauth` (
    `proveedor` VARCHAR(40) NOT NULL,
    `cuenta_email` VARCHAR(254) NULL,
    `access_token_cifrado` BLOB NOT NULL,
    `refresh_token_cifrado` BLOB NOT NULL,
    `token_expira_at` DATETIME NOT NULL,
    `scopes` TEXT NOT NULL,
    `recurso_id` VARCHAR(255) NOT NULL DEFAULT 'primary',
    `estado` VARCHAR(20) NOT NULL DEFAULT 'activo',
    `conectado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `actualizado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`proveedor`),
    CONSTRAINT `chk_integracion_proveedor`
        CHECK (`proveedor` IN ('google_calendar')),
    CONSTRAINT `chk_integracion_estado`
        CHECK (`estado` IN ('activo', 'error', 'desconectado'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `reserva_calendario_eventos` (
    `reserva_id` INT NOT NULL,
    `proveedor` VARCHAR(40) NOT NULL DEFAULT 'google_calendar',
    `evento_id` VARCHAR(255) NULL,
    `evento_url` VARCHAR(1000) NULL,
    `sync_estado` VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    `ultimo_error` VARCHAR(500) NULL,
    `sincronizado_at` DATETIME NULL,
    `actualizado_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`reserva_id`, `proveedor`),
    KEY `idx_calendario_sync_estado` (`proveedor`, `sync_estado`),
    CONSTRAINT `fk_calendario_reserva`
        FOREIGN KEY (`reserva_id`) REFERENCES `reservas` (`id`)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT `chk_calendario_proveedor`
        CHECK (`proveedor` IN ('google_calendar')),
    CONSTRAINT `chk_calendario_sync_estado`
        CHECK (`sync_estado` IN ('pendiente', 'sincronizado', 'error', 'eliminado'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO `schema_migrations` (`version`, `descripcion`)
VALUES (
    '20260819_01',
    'Integridad del esquema, relaciones con clientes y preparación para acceso social'
);

INSERT IGNORE INTO `schema_migrations` (`version`, `descripcion`)
VALUES (
    '20260819_02',
    'Reservas grupales y un único cliente por fecha y hora activas'
);

INSERT IGNORE INTO `schema_migrations` (`version`, `descripcion`)
VALUES (
    '20260819_03',
    'Modalidades regular e institucional con agenda segura por intervalos'
);

INSERT IGNORE INTO `schema_migrations` (`version`, `descripcion`)
VALUES (
    '20260819_04',
    'OAuth social, Turnstile y sincronización cifrada con Google Calendar'
);

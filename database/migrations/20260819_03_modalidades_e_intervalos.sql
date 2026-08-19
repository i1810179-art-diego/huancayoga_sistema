-- Huancayoga
-- Migración 20260819_03: modalidades de reserva e intervalos sin cruces.

ALTER TABLE reservas
    DROP CHECK chk_reservas_cantidad_personas,
    ADD COLUMN tipo_reserva VARCHAR(20) NOT NULL DEFAULT 'regular'
        AFTER cliente_id,
    ADD COLUMN duracion_minutos SMALLINT UNSIGNED NOT NULL DEFAULT 60
        AFTER hora,
    ADD COLUMN tipo_lugar VARCHAR(20) NOT NULL DEFAULT 'local'
        AFTER duracion_minutos,
    ADD COLUMN direccion_externa VARCHAR(255) NULL
        AFTER tipo_lugar,
    ADD KEY idx_reservas_agenda
        (fecha, hora, estado),
    ADD CONSTRAINT chk_reservas_cantidad_personas
        CHECK (cantidad_personas BETWEEN 1 AND 40),
    ADD CONSTRAINT chk_reservas_tipo
        CHECK (tipo_reserva IN ('regular', 'institucional')),
    ADD CONSTRAINT chk_reservas_duracion
        CHECK (duracion_minutos BETWEEN 15 AND 240),
    ADD CONSTRAINT chk_reservas_lugar
        CHECK (tipo_lugar IN ('local', 'externo')),
    ADD CONSTRAINT chk_reservas_direccion
        CHECK (
            tipo_lugar = 'local'
            OR (
                direccion_externa IS NOT NULL
                AND CHAR_LENGTH(TRIM(direccion_externa)) >= 5
            )
        ),
    ADD CONSTRAINT chk_reservas_mismo_dia
        CHECK (TIME_TO_SEC(hora) + duracion_minutos * 60 <= 86400);

UPDATE reservas r
INNER JOIN servicios s ON s.id = r.servicio_id
SET r.duracion_minutos = LEAST(240, GREATEST(15, s.duracion_minutos)),
    r.tipo_reserva = 'regular',
    r.tipo_lugar = 'local',
    r.direccion_externa = NULL;

CREATE TABLE reserva_programa_detalles (
    reserva_id INT NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    nombre_organizacion VARCHAR(150) NOT NULL,
    rango_edad VARCHAR(80) NULL,
    necesidades_apoyo TEXT NULL,
    creado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (reserva_id),
    KEY idx_programa_categoria_organizacion
        (categoria, nombre_organizacion),
    CONSTRAINT fk_programa_reserva
        FOREIGN KEY (reserva_id) REFERENCES reservas (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_programa_categoria
        CHECK (
            categoria IN (
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
    CONSTRAINT chk_programa_organizacion
        CHECK (CHAR_LENGTH(TRIM(nombre_organizacion)) >= 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Cada fila representa cinco minutos ocupados. La clave primaria hace que
-- MySQL rechace dos reservas superpuestas incluso si llegan al mismo tiempo.
CREATE TABLE reserva_bloques_horario (
    fecha DATE NOT NULL,
    hora_bloque TIME NOT NULL,
    reserva_id INT NOT NULL,
    PRIMARY KEY (fecha, hora_bloque),
    UNIQUE KEY uq_bloque_reserva (reserva_id, hora_bloque),
    CONSTRAINT fk_bloque_reserva
        FOREIGN KEY (reserva_id) REFERENCES reservas (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Reconstruye la agenda para reservas activas existentes. Se redondean
-- horarios antiguos al bloque inferior y el final al bloque superior.
INSERT INTO reserva_bloques_horario (fecha, hora_bloque, reserva_id)
WITH RECURSIVE secuencia (numero) AS (
    SELECT 0
    UNION ALL
    SELECT numero + 1
    FROM secuencia
    WHERE numero < 287
)
SELECT
    r.fecha,
    SEC_TO_TIME(
        FLOOR(TIME_TO_SEC(r.hora) / 300) * 300
        + secuencia.numero * 300
    ),
    r.id
FROM reservas r
INNER JOIN secuencia
    ON secuencia.numero < CEIL(
        (
            MOD(TIME_TO_SEC(r.hora), 300)
            + r.duracion_minutos * 60
        ) / 300
    )
WHERE r.estado IN ('pendiente', 'confirmada');

INSERT INTO schema_migrations (version, descripcion)
VALUES (
    '20260819_03',
    'Modalidades regular e institucional con agenda segura por intervalos'
);

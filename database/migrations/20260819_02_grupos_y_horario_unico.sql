-- Huancayoga
-- Migración 20260819_02: reservas grupales y un cliente por horario.

-- Las reservas activas con fecha pasada son datos inválidos para la agenda.
-- Se conservan como registros cancelados, sin eliminar ninguna fila.
UPDATE reservas
SET estado = 'cancelada'
WHERE fecha < CURDATE()
  AND estado IN ('pendiente', 'confirmada');

ALTER TABLE reservas
    ADD COLUMN cantidad_personas SMALLINT UNSIGNED NOT NULL DEFAULT 1
        AFTER servicio_id,
    ADD COLUMN horario_activo_fecha DATE
        GENERATED ALWAYS AS (
            CASE
                WHEN estado IN ('pendiente', 'confirmada') THEN fecha
                ELSE NULL
            END
        ) STORED,
    ADD COLUMN horario_activo_hora TIME
        GENERATED ALWAYS AS (
            CASE
                WHEN estado IN ('pendiente', 'confirmada') THEN hora
                ELSE NULL
            END
        ) STORED,
    ADD CONSTRAINT chk_reservas_cantidad_personas
        CHECK (cantidad_personas > 0),
    ADD CONSTRAINT uq_reservas_horario_activo
        UNIQUE (horario_activo_fecha, horario_activo_hora);

INSERT INTO schema_migrations (version, descripcion)
VALUES (
    '20260819_02',
    'Reservas grupales y un único cliente por fecha y hora activas'
);

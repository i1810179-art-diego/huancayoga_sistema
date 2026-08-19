-- Huancayoga
-- Migración 20260819_04: credenciales OAuth del calendario y relación de eventos.

CREATE TABLE integraciones_oauth (
    proveedor VARCHAR(40) NOT NULL,
    cuenta_email VARCHAR(254) NULL,
    access_token_cifrado BLOB NOT NULL,
    refresh_token_cifrado BLOB NOT NULL,
    token_expira_at DATETIME NOT NULL,
    scopes TEXT NOT NULL,
    recurso_id VARCHAR(255) NOT NULL DEFAULT 'primary',
    estado VARCHAR(20) NOT NULL DEFAULT 'activo',
    conectado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (proveedor),
    CONSTRAINT chk_integracion_proveedor
        CHECK (proveedor IN ('google_calendar')),
    CONSTRAINT chk_integracion_estado
        CHECK (estado IN ('activo', 'error', 'desconectado'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE reserva_calendario_eventos (
    reserva_id INT NOT NULL,
    proveedor VARCHAR(40) NOT NULL DEFAULT 'google_calendar',
    evento_id VARCHAR(255) NULL,
    evento_url VARCHAR(1000) NULL,
    sync_estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    ultimo_error VARCHAR(500) NULL,
    sincronizado_at DATETIME NULL,
    actualizado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (reserva_id, proveedor),
    KEY idx_calendario_sync_estado (proveedor, sync_estado),
    CONSTRAINT fk_calendario_reserva
        FOREIGN KEY (reserva_id) REFERENCES reservas (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_calendario_proveedor
        CHECK (proveedor IN ('google_calendar')),
    CONSTRAINT chk_calendario_sync_estado
        CHECK (sync_estado IN ('pendiente', 'sincronizado', 'error', 'eliminado'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO schema_migrations (version, descripcion)
VALUES (
    '20260819_04',
    'OAuth social, Turnstile y sincronización cifrada con Google Calendar'
);

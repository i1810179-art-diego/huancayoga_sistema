# Acceso social, Turnstile y Google Calendar

La integración separa dos responsabilidades:

- Google, Facebook y TikTok permiten identificar al cliente después de ingresar su DNI.
- Google Calendar se conecta únicamente desde el panel de la dueña y no usa la cuenta del cliente.

Los tokens de acceso social son efímeros y no se almacenan. Los tokens de Google Calendar se guardan cifrados en MySQL.

## Variables de Render

Configurar en **Render > Web Service > Environment**:

```text
APP_BASE_URL=https://TU-DOMINIO
OAUTH_TIMEOUT=12
OAUTH_TOKEN_ENCRYPTION_KEY=UNA_CLAVE_ALEATORIA_LARGA_Y_EXCLUSIVA

TURNSTILE_ENABLED=True
TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...
TURNSTILE_EXPECTED_HOSTNAME=TU-DOMINIO-SIN-HTTPS
TURNSTILE_TIMEOUT=8

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_CALENDAR_ID=primary

FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
FACEBOOK_GRAPH_VERSION=VERSION_HABILITADA_EN_META

TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
```

No agregar comillas ni espacios alrededor de los valores. `OAUTH_TOKEN_ENCRYPTION_KEY` debe ser distinta de las claves de los proveedores y no debe cambiarse mientras existan tokens cifrados.

## Cloudflare Turnstile

Crear un widget para el dominio público de Huancayoga y copiar su **Site key** y **Secret key**. La aplicación muestra el widget en:

- acceso de clientes;
- registro de clientes;
- acceso administrativo.

La respuesta se valida siempre en el servidor antes de aceptar las credenciales o iniciar OAuth.

## Google OAuth y Calendar

En Google Cloud:

1. Configurar la pantalla de consentimiento OAuth.
2. Habilitar **Google Calendar API**.
3. Crear un cliente OAuth de tipo **Web application**.
4. Registrar exactamente estas URL de redirección:

```text
https://TU-DOMINIO/cliente/oauth/google/callback
https://TU-DOMINIO/admin/integraciones/google-calendar/callback
```

Después del despliegue, la dueña debe ingresar a:

```text
https://TU-DOMINIO/admin/integraciones/google-calendar
```

y seleccionar **Conectar Google Calendar**. Las reservas confirmadas nuevas se sincronizan automáticamente. El panel permite reintentar reservas pendientes o con error.

## Facebook Login

En Meta for Developers, crear o usar una aplicación con Facebook Login para web y registrar:

```text
https://TU-DOMINIO/cliente/oauth/facebook/callback
```

Copiar el App ID, App Secret y definir en `FACEBOOK_GRAPH_VERSION` la versión activa configurada en la aplicación. Facebook puede no entregar correo; Huancayoga lo solicitará cuando falte.

## TikTok Login Kit

En TikTok for Developers, habilitar Login Kit para web, solicitar `user.info.basic` y registrar exactamente:

```text
https://TU-DOMINIO/cliente/oauth/tiktok/callback
```

TikTok no entrega correo con ese alcance. Después de autenticar, Huancayoga pide el correo y los datos faltantes antes de terminar el registro.

## Base de datos

Aplicar en orden las migraciones de `database/migrations/`. Para estas integraciones deben estar registradas:

```text
20260819_01
20260819_02
20260819_03
20260819_04
```

La migración `20260819_04_oauth_turnstile_calendar.sql` crea el almacenamiento cifrado del calendario y la relación entre reservas y eventos.

## Comportamiento ante fallos

- Una falla de Google Calendar no revierte ni elimina una reserva confirmada.
- La reserva queda como `pendiente` o `error` de sincronización para reintentarla.
- Al cancelar una reserva, el sistema intenta retirar el evento de Calendar.
- Al desconectar Calendar, las reservas de Huancayoga se conservan intactas.

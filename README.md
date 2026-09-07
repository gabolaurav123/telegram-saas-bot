# Telegram Premium Memberships SaaS

Sistema profesional para vender y administrar membresias premium de Telegram mediante un bot avanzado con aprobacion manual de pagos, accesos temporales, multiples planes, multiples administradores, multiples canales/grupos y control automatico de vencimientos.

## Stack

- Python 3.12+
- aiogram 3.28.0
- PostgreSQL
- SQLAlchemy 2 async + asyncpg
- Alembic
- APScheduler
- Railway/Seenode-ready

## Estructura

```text
app/
  config/        Configuracion y logging
  database/      Engine, sesiones async y metadata
  filters/       Filtros de permisos
  handlers/      Flujos de Telegram para usuarios y admins
  keyboards/     Inline keyboards
  middlewares/   DB session y rate limiting
  models/        Modelos SQLAlchemy
  scheduler/     Jobs de vencimientos, recordatorios y backups
  services/      Reglas de negocio
  states/        FSM aiogram
  utils/         Utilidades compartidas
  logs/          Logs locales rotativos
  media/         Espacio para media futura
main.py
alembic.ini
migrations/
Procfile
runtime.txt
requirements.txt
.env.example
```

## Funciones principales

- Registro automatico en `/start`.
- Menu inline movil: planes, compra, estado, soporte, FAQ, idioma, Mini App y renovacion.
- Flujo de compra por plan y metodo de pago.
- Mensajes personalizados por plan y metodo con variables:
  `{username}`, `{plan_name}`, `{price}`, `{duration}`, `{payment_method}`, `{instructions}`.
- Recepcion de comprobantes como imagen o documento.
- Notificacion automatica a OWNER/ADMIN con botones: aprobar, rechazar, banear y contactar.
- Aprobacion manual con generacion de enlaces temporales de un solo uso.
- Links de aprobacion validos al menos 10 horas, con revocacion automatica solo tras join confirmado.
- Deteccion real de joins por invite link, logs a admins y auditoria en base de datos.
- Reemision manual de links expirados sin join con `/reissuelink ID`.
- Rechazo con motivo opcional y notificacion al usuario.
- CRM interno: `chat_id`, source/campaign/referral, estado comercial, tags, notas, VIP, historial y estado de entrega.
- Antifraude de comprobantes: hash SHA-256, hash perceptual para imagenes y alertas de duplicados/similitud.
- Telegram Stars como metodo de pago nativo opcional; convierte primero el precio del plan a USD y despues a XTR.
- Arquitectura preparada para pagos externos alojados mediante sesiones y webhooks idempotentes.
- Roles estrictos: OWNER, SUPERVISOR, ADMIN, PAYMENTS, SUPPORT, SALES, MODERATOR, READ_ONLY.
- Gestion de planes, metodos de pago, administradores, canales y grupos.
- Metodos de pago configurables por plan desde `/settings -> Planes -> Metodos del plan`.
- Registro automatico de canales/grupos cuando el bot es agregado como administrador.
- Scheduler para recordatorios a 3 dias, 1 dia y expiracion.
- Recordatorios con boton "Renovar ahora"; la renovacion siempre requiere comprobante y aprobacion manual.
- Expulsion automatica de usuarios vencidos con log a admins y eventos de acceso.
- Logs de auditoria en base de datos y archivo local.
- Exportacion CSV en ZIP desde el panel de backups.
- Log automatico a admins cuando un usuario entra por primera vez con `/start`.
- Generacion administrativa de hasta 100 links por lote, por plan/chat, desde el acceso directo `Links de acceso` en `/settings` o con `/addmember`; cada link admite un usuario y vence con el plan.
- Broadcast por segmentos con `/broadcast`, batches, retries y resumen final.
- Exportacion de clientes CSV/XLSX con `/exportclients`.
- Soporte privado: mensajes de usuarios reenviados a admins y respuestas por reply con prioridad sobre formularios administrativos abandonados.
- Admin inbox con asignacion, resolucion, contadores de no leidos y persistencia de mensajes.
- Quick replies configurables para soporte.
- Motor de automatizaciones con reglas, jobs, dedupe y ejecucion desde scheduler.
- Cupones, referrals, campaigns y funnel events listos para growth/retention.
- Selector de idioma persistente con `/language`.
- Mini Apps cliente/admin servidas por el mismo proceso, autenticadas con `initData` y conectadas a PostgreSQL.
- Boton de menu persistente y catalogo de comandos configurados automaticamente por rol en cada arranque.
- Panel `/settings` condensado por areas, acceso directo a links, pendientes navegables, cupones guiados y configuracion persistente.

## Variables de entorno

Copia `.env.example` a `.env` en desarrollo local:

```bash
cp .env.example .env
```

Variables minimas:

```env
BOT_TOKEN=123456:telegram_bot_token
DATABASE_URL=postgresql://user:password@host:5432/database
OWNER_ID=123456789
# OWNER_IDS=123456789,987654321
```

`OWNER_ID` sirve para un propietario. `OWNER_IDS` acepta una lista separada por comas. Esos usuarios tienen control total aunque aun no existan en la tabla `admins`.

Las URLs de Neon/Railway con `sslmode=require` son aceptadas; el sistema normaliza ese parametro internamente para `asyncpg`.

Variables avanzadas agregadas:

```env
DEFAULT_LANGUAGE=es
SUPPORTED_LANGUAGES=["es","en","pt"]
DEFAULT_CURRENCY=USD
CURRENCY_USD_RATES={"USD":"1","MXN":"0.05926","BOB":"0.145","EUR":"1.08","COP":"0.00025","ARS":"0.001"}
RECEIPT_MAX_DOWNLOAD_MB=20
AI_ENABLED=false
OCR_ENABLED=false
SMART_REPLIES_ENABLED=false
TELEGRAM_STARS_ENABLED=true
TELEGRAM_STARS_PER_USD=44.11764706
TELEGRAM_STARS_DEFAULT_RATIO=44.11764706
EXTERNAL_PAYMENTS_ENABLED=false
EXTERNAL_PAYMENT_WEBHOOK_SECRET=
MINI_APP_CLIENT_URL=https://tu-servicio.seenode.app/miniapp
MINI_APP_ADMIN_URL=https://tu-servicio.seenode.app/admin
TELEGRAM_WEBHOOK_SECRET_TOKEN=
WEB_ENABLED=true
WEB_HOST=0.0.0.0
PORT=8000
TELEGRAM_WEBAPP_MAX_AGE_SECONDS=86400
```

`CURRENCY_USD_RATES` usa el valor en USD de 1 unidad de cada moneda. Ejemplo: si un plan cuesta
`220 MXN` y `MXN=0.05926`, el bot calcula `13.04 USD`; con la referencia
`1500 Stars / 34 USD = 44.11764706 Stars/USD`, la factura sera de `575 XTR`,
no de `220 XTR`, `1304 XTR` ni `220 USD`.

Para monedas distintas de USD, si no existe tasa configurada el bot no crea la factura de Stars.
Esto evita cobrar mal por interpretar pesos, bolivianos u otra moneda como dolares.

Si una URL Mini App queda vacia, el bot oculta ese boton para no presentar una accion rota.
Las tasas, Stars/USD, marca, soporte, FAQ e idioma predeterminado tambien se pueden editar desde
`/settings -> Sistema -> Configuracion`; se guardan en PostgreSQL y sobreviven al redeploy.

## Instalacion local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

En Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

## Flujo inicial recomendado

1. Crea el bot con BotFather y configura `BOT_TOKEN`.
2. Define tu Telegram ID en `OWNER_ID`.
3. Ejecuta `/start` con el OWNER.
4. Abre `/settings`.
5. Crea planes desde `Planes`.
6. Configura metodos de pago desde `Metodos de pago`.
7. Agrega el bot como admin en los canales/grupos privados.
8. Si Telegram no envia el evento automaticamente, ejecuta `/register_chat` dentro del grupo o registra el chat manualmente desde el panel.
9. Vincula canales/grupos a cada plan.
10. Personaliza mensajes por metodo de pago.

## Permisos por rol

- `OWNER`: control total, admins, configuracion, backups.
- `SUPERVISOR`: gestion operativa amplia sin ser owner por entorno.
- `ADMIN`: pagos, planes, metodos, canales, estadisticas, usuarios y logs.
- `PAYMENTS`: revision de pagos y estadisticas.
- `SUPPORT`: soporte e inbox.
- `SALES`: estadisticas, broadcast y contacto directo.
- `MODERATOR`: soporte basico.
- `READ_ONLY`: lectura de metricas segun permisos.

## Railway

1. Crea un proyecto en Railway.
2. Agrega un servicio PostgreSQL.
3. Agrega este repositorio como servicio web de larga duracion.
4. Configura variables:

```env
BOT_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
OWNER_ID=123456789
APP_ENV=production
PUBLIC_BRAND_NAME=Tu Marca Premium
SUPPORT_URL=https://t.me/tu_soporte
SCHEDULER_ENABLED=true
MINI_APP_CLIENT_URL=https://tu-dominio.up.railway.app/miniapp
MINI_APP_ADMIN_URL=https://tu-dominio.up.railway.app/admin
WEB_ENABLED=true
```

5. Railway ejecutara:

```text
alembic upgrade head && python main.py
```

El bot usa polling, pero las Mini Apps necesitan el dominio HTTPS publico del mismo servicio.

## Seenode

Configura el servicio como aplicacion web de larga duracion. El mismo proceso atiende el puerto
HTTP de Seenode y mantiene el polling del bot:

```text
pip install -r requirements.txt
alembic upgrade head && python main.py
```

Variables minimas en Seenode:

```env
BOT_TOKEN=...
DATABASE_URL=...
OWNER_ID=8795701121
APP_ENV=production
SCHEDULER_ENABLED=true
LOG_TO_FILE=true
MINI_APP_CLIENT_URL=https://tu-servicio.seenode.app/miniapp
MINI_APP_ADMIN_URL=https://tu-servicio.seenode.app/admin
WEB_ENABLED=true
TELEGRAM_STARS_PER_USD=44.11764706
```

Seenode inyecta `PORT`; no fijes otro puerto en produccion. Comprueba el despliegue en `/health`.
Cuando las URLs estan configuradas, el arranque registra automaticamente el boton permanente de
Mini App para clientes y el boton de panel para cada OWNER/ADMIN conocido.

No ejecutes otra instancia local con el mismo `BOT_TOKEN` mientras Seenode hace polling.

## Base de datos

Las tablas principales son:

- `users`
- `admins`
- `plans`
- `payment_methods`
- `plan_payment_messages`
- `payment_requests`
- `memberships`
- `channels`
- `groups`
- `logs`
- `settings`
- `notifications`
- `statistics`
- `generated_invite_links`
- `membership_access_events`

Las asociaciones many-to-many son:

- `plan_channels`
- `plan_groups`
- `plan_payment_methods`

La migracion inicial esta en `migrations/versions/0001_initial.py` y crea el esquema completo desde la metadata de SQLAlchemy.

## Seguridad operacional

- Valida roles en cada accion administrativa.
- Usa rate limiting en mensajes y callbacks.
- Evita comprobantes duplicados pendientes por usuario/plan.
- Usa enlaces temporales de un solo uso, nunca links permanentes.
- Los links aprobados no expiran en minutos: duran minimo 10 horas y se revocan cuando Telegram confirma el ingreso.
- Las renovaciones no extienden membresias automaticamente; siempre crean una nueva solicitud de pago pendiente.
- Expulsa usuarios vencidos con `ban_chat_member` + `unban_chat_member`.
- Registra aprobaciones, rechazos, expulsiones, errores administrativos y backups.

## Comandos

Usuario:

- `/start`
- `/help`
- `/id`
- `/profile`
- `/plans`
- `/language`
- `/support`
- `/paysupport`

Administracion:

- `/settings`
- `/register_chat` dentro de un grupo/canal donde el bot sea admin
- `/stats`
- `/addmember`
- `/listlinks`
- `/revokelink ID`
- `/reissuelink ID`
- `/linkstats`
- `/userinfo TELEGRAM_ID`
- `/broadcast`
- `/exportclients`
- `/inbox`
- `/quickreplies`

## Migraciones recientes

- `0002_growth_tools`: invite links, broadcast y ticket-lite.
- `0003_broadcast_bigint_chat_id`: soporte de chat IDs grandes en broadcast.
- `0004_access_events`: tracking real de joins, leaves, kicks y reemision de links.
- `0005_crm_growth`: CRM, inbox persistente, quick replies, antifraude, Telegram Stars, pagos externos, cupones, referrals, campaigns y automations.
- `0007_user_language_currency`: idioma preferido por usuario y soporte de configuracion USD/Stars.

## Telegram Stars

Para activar Stars:

1. Mantén `TELEGRAM_STARS_ENABLED=true`.
2. Activa el metodo `Telegram Stars` en los planes correspondientes.
3. Define `TELEGRAM_STARS_PER_USD` segun tu estrategia de precios.
4. Define `CURRENCY_USD_RATES` para cada moneda usada por tus planes.
5. Opcionalmente define `stars_amount` dentro de `plans.metadata_json` para controlar el precio exacto en Stars.

Calculo:

```text
precio_plan_en_moneda_original * tasa_USD_de_la_moneda * TELEGRAM_STARS_PER_USD = XTR
```

Ejemplo:

```text
220 MXN * 0.05926 USD/MXN * 44.11764706 Stars/USD = 575 XTR
```

Si el plan usa una moneda distinta de USD y no hay tasa configurada, el bot rechaza la factura
en vez de cobrar mal.

El invoice usa `currency=XTR` y `provider_token` vacio, como requiere Telegram para Stars. Documentacion: [Telegram Bot API Payments](https://core.telegram.org/bots/api#payments).

## Notas de produccion

- El bot debe ser administrador de cada canal/grupo privado para crear links y expulsar usuarios.
- Si rotas o reemplazas el bot en BotFather, actualiza `BOT_TOKEN` en el proveedor de despliegue y vuelve a agregar el nuevo bot como admin en cada canal/grupo. El panel `System health` muestra el bot ID activo y audita permisos de invite links, expulsiones y mensajes por chat registrado.
- Los backups generados en Railway pueden no persistir tras redeploy; usa el boton de backup para descargar el ZIP cuando lo necesites.
- Para volumen alto, usa un PostgreSQL con pool suficiente y configura `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`.
- Si migras a webhook en el futuro, separa el scheduler en un worker unico para evitar jobs duplicados.

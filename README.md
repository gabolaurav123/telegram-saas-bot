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
- Menu inline movil: planes, compra, estado, soporte, FAQ y renovacion.
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
- Telegram Stars como metodo de pago nativo opcional; el flujo manual sigue disponible.
- Arquitectura preparada para pagos externos alojados mediante sesiones y webhooks idempotentes.
- Roles estrictos: OWNER, SUPERVISOR, ADMIN, PAYMENTS, SUPPORT, SALES, MODERATOR, READ_ONLY.
- Gestion de planes, metodos de pago, administradores, canales y grupos.
- Registro automatico de canales/grupos cuando el bot es agregado como administrador.
- Scheduler para recordatorios a 3 dias, 1 dia y expiracion.
- Recordatorios con boton "Renovar ahora"; la renovacion siempre requiere comprobante y aprobacion manual.
- Expulsion automatica de usuarios vencidos con log a admins y eventos de acceso.
- Logs de auditoria en base de datos y archivo local.
- Exportacion CSV en ZIP desde el panel de backups.
- Log automatico a admins cuando un usuario entra por primera vez con `/start`.
- Generacion administrativa de invite links por plan/chat con `/addmember`, `/listlinks`, `/revokelink` y `/linkstats`.
- Broadcast por segmentos con `/broadcast`, batches, retries y resumen final.
- Exportacion de clientes CSV/XLSX con `/exportclients`.
- Soporte privado: mensajes de usuarios reenviados a admins y respuestas por reply.
- Admin inbox con asignacion, resolucion, contadores de no leidos y persistencia de mensajes.
- Quick replies configurables para soporte.
- Motor de automatizaciones con reglas, jobs, dedupe y ejecucion desde scheduler.
- Cupones, referrals, campaigns y funnel events listos para growth/retention.
- Validador de Telegram Mini App `initData` para futuras Mini Apps cliente/admin.

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
RECEIPT_MAX_DOWNLOAD_MB=20
AI_ENABLED=false
OCR_ENABLED=false
SMART_REPLIES_ENABLED=false
TELEGRAM_STARS_ENABLED=true
TELEGRAM_STARS_DEFAULT_RATIO=1
EXTERNAL_PAYMENTS_ENABLED=false
EXTERNAL_PAYMENT_WEBHOOK_SECRET=
MINI_APP_CLIENT_URL=
MINI_APP_ADMIN_URL=
TELEGRAM_WEBHOOK_SECRET_TOKEN=
```

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
3. Agrega este repositorio como servicio worker.
4. Configura variables:

```env
BOT_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
OWNER_ID=123456789
APP_ENV=production
PUBLIC_BRAND_NAME=Tu Marca Premium
SUPPORT_URL=https://t.me/tu_soporte
SCHEDULER_ENABLED=true
```

5. Railway ejecutara:

```text
alembic upgrade head && python main.py
```

El proyecto usa polling, por lo que no requiere dominio publico ni webhook.

## Seenode

Configura el servicio como worker/bot de larga duracion:

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
```

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

## Telegram Stars

Para activar Stars:

1. Mantén `TELEGRAM_STARS_ENABLED=true`.
2. Activa el metodo `Telegram Stars` en los planes correspondientes.
3. Opcionalmente define `stars_amount` dentro de `plans.metadata_json` para controlar el precio exacto en Stars.

El invoice usa `currency=XTR` y `provider_token` vacio, como requiere Telegram para Stars. Documentacion: [Telegram Bot API Payments](https://core.telegram.org/bots/api#payments).

## Notas de produccion

- El bot debe ser administrador de cada canal/grupo privado para crear links y expulsar usuarios.
- Si rotas o reemplazas el bot en BotFather, actualiza `BOT_TOKEN` en el proveedor de despliegue y vuelve a agregar el nuevo bot como admin en cada canal/grupo. El panel `System health` muestra el bot ID activo y audita permisos de invite links, expulsiones y mensajes por chat registrado.
- Los backups generados en Railway pueden no persistir tras redeploy; usa el boton de backup para descargar el ZIP cuando lo necesites.
- Para volumen alto, usa un PostgreSQL con pool suficiente y configura `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`.
- Si migras a webhook en el futuro, separa el scheduler en un worker unico para evitar jobs duplicados.

# Telegram Premium Memberships SaaS

Sistema profesional para vender y administrar membresias premium de Telegram mediante un bot avanzado con aprobacion manual de pagos, accesos temporales, multiples planes, multiples administradores, multiples canales/grupos y control automatico de vencimientos.

## Stack

- Python 3.12+
- aiogram 3.28.0
- PostgreSQL
- SQLAlchemy 2 async + asyncpg
- Alembic
- APScheduler
- Railway-ready

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
- Rechazo con motivo opcional y notificacion al usuario.
- Roles estrictos: OWNER, ADMIN, MODERATOR.
- Gestion de planes, metodos de pago, administradores, canales y grupos.
- Registro automatico de canales/grupos cuando el bot es agregado como administrador.
- Scheduler para recordatorios a 3 dias, 1 dia y expiracion.
- Expulsion automatica de usuarios vencidos.
- Logs de auditoria en base de datos y archivo local.
- Exportacion CSV en ZIP desde el panel de backups.
- Log automatico a admins cuando un usuario entra por primera vez con `/start`.
- Generacion administrativa de invite links por plan/chat con `/addmember`, `/listlinks`, `/revokelink` y `/linkstats`.
- Broadcast por segmentos con `/broadcast`, batches, retries y resumen final.
- Exportacion de clientes CSV/XLSX con `/exportclients`.
- Soporte privado: mensajes de usuarios reenviados a admins y respuestas por reply.

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
- `ADMIN`: pagos, planes, metodos, canales, estadisticas, usuarios y logs.
- `MODERATOR`: acceso basico de soporte.

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

Administracion:

- `/settings`
- `/register_chat` dentro de un grupo/canal donde el bot sea admin
- `/stats`
- `/addmember`
- `/listlinks`
- `/revokelink ID`
- `/linkstats`
- `/broadcast`
- `/exportclients`

## Notas de produccion

- El bot debe ser administrador de cada canal/grupo privado para crear links y expulsar usuarios.
- Los backups generados en Railway pueden no persistir tras redeploy; usa el boton de backup para descargar el ZIP cuando lo necesites.
- Para volumen alto, usa un PostgreSQL con pool suficiente y configura `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`.
- Si migras a webhook en el futuro, separa el scheduler en un worker unico para evitar jobs duplicados.

# API de Control y Gestión de Equipos v1.1.0

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.115.12-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0-d71f00?style=for-the-badge&logo=sqlalchemy" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/PostgreSQL-17-336791?style=for-the-badge&logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Docker-27.5.1-2496ED?style=for-the-badge&logo=docker" alt="Docker Ready">
</p>

<p align="center">
  <i>Una solución backend robusta y escalable para el Sistema de Control y Gestión de Equipos Físicos, Inventario, Licencias y Reservas.</i>
</p>

---

## 📋 Tabla de Contenidos

- [API de Control y Gestión de Equipos v1.1.0](#api-de-control-y-gestión-de-equipos-v110)
  - [📋 Tabla de Contenidos](#-tabla-de-contenidos)
  - [📌 Acerca del Proyecto](#-acerca-del-proyecto)
  - [🚀 Funcionalidades Principales](#-funcionalidades-principales)
  - [🛠️ Tecnologías Utilizadas](#️-tecnologías-utilizadas)
  - [🏁 Configuración y Ejecución](#-configuración-y-ejecución)
    - [Prerrequisitos](#prerrequisitos)
    - [Variables de Entorno](#variables-de-entorno)
    - [Base de Datos](#base-de-datos)
    - [Instalación de Dependencias](#instalación-de-dependencias)
    - [Ejecución (Desarrollo)](#ejecución-desarrollo)
    - [Ejecución (Docker - Recomendado)](#ejecución-docker---recomendado)
  - [📚 Documentación de la API](#-documentación-de-la-api)
  - [📁 Estructura del Proyecto](#-estructura-del-proyecto)
  - [📝 TODO / Mejoras Futuras](#-todo--mejoras-futuras)
  - [🤝 Contribuciones](#-contribuciones)
  - [📄 Licencia](#-licencia)
  - [📧 Contacto](#-contacto)

---

## 📌 Acerca del Proyecto

**Control de Equipos API** es un sistema backend diseñado para centralizar y simplificar la administración de activos de TI y físicos en una organización. Proporciona una API RESTful completa que permite realizar un seguimiento detallado del ciclo de vida de los equipos, gestionar el inventario de consumibles, administrar licencias de software, programar mantenimientos preventivos y correctivos, y manejar un sistema de reservas de equipos.

El proyecto está construido siguiendo las mejores prácticas de desarrollo de software, con una arquitectura modular y desacoplada que facilita su mantenimiento y escalabilidad.

---

## 🚀 Funcionalidades Principales

- **Gestión de Activos:** CRUD completo para Equipos y sus Componentes.
- **Movimientos de Equipos:** Registro y seguimiento de traslados, asignaciones, etc.
- **Mantenimientos:** Programación y registro de mantenimientos preventivos y correctivos.
- **Documentación:** Gestión de documentación asociada a equipos, licencias o mantenimientos.
- **Control de Inventario:** Administración de catálogos de consumibles/partes, control de stock y registro de movimientos.
- **Licencias:** Gestión de Catálogo de Software, Licencias Adquiridas y asignación a Equipos o Usuarios.
- **Reservas:** Sistema de Reservas de Equipos por franjas horarias.
- **RBAC:** Gestión de Usuarios, Roles y Permisos para un control de acceso granular.
- **Catálogos:** Administración de catálogos configurables (Proveedores, Estados, Tipos de Documento, etc.).
- **Notificaciones:** Sistema de notificaciones internas.
- **Auditoría y Logs:** Logs de Acceso y Auditoría de cambios, con endpoints para consultarlos.
- **Dashboard:** Endpoint que provee métricas clave para una vista rápida del estado del sistema.
- **Autenticación:** Sistema seguro basado en JWT (OAuth2 Password Flow).

---

## 🛠️ Tecnologías Utilizadas

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/)
- **Base de Datos:** [PostgreSQL](https://www.postgresql.org/)
- **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/) (con `asyncio` a través de `asyncpg`)
- **Validación de Datos:** [Pydantic](https://pydantic-docs.helpmanual.io/)
- **Migraciones de BD:** [Alembic](https://alembic.sqlalchemy.org/)
- **Autenticación:** JWT (OAuth2 Password Flow)
- **Contenerización:** [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- **Tareas en Segundo Plano:** [Celery](https://docs.celeryq.dev/) con [Redis](https://redis.io/) como broker.

---

## 🏁 Configuración y Ejecución

### Prerrequisitos

- Python 3.13+
- PostgreSQL Server (ej: v16+)
- Redis (Opcional, si se usa Celery para tareas de fondo)
- Docker y Docker Compose (Recomendado para fácil despliegue)

### Variables de Entorno

1. Copia el archivo `.env.example` a un nuevo archivo llamado `.env`.
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` y configura las variables, especialmente:
   - `SECRET_KEY`: Genera una clave segura (puedes usar `openssl rand -hex 32`).
   - `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: Datos de tu base de datos PostgreSQL.
   - `BACKEND_CORS_ORIGINS`: Lista separada por comas de los orígenes de tu frontend (ej: `http://localhost:3000,http://127.0.0.1:3000`).
   - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: URLs de tu broker/backend Celery (ej: Redis).

### Base de Datos

- Asegúrate de que el servidor PostgreSQL esté corriendo y la base de datos (`POSTGRES_DB`) exista.
- **Creación de Estructura:**
  - Ejecuta el script `structureControlEquipos.sql` en tu base de datos para crear todas las tablas, funciones, triggers, etc.
- **Migraciones (Alembic):**
  - (Alternativa al script SQL) Configura `alembic.ini` (ya apunta a `.env`).
  - Aplica las migraciones: `alembic upgrade head`
  - Si creaste la BD con el script SQL, puedes 'sellar' Alembic para que no intente crear las tablas de nuevo: `alembic stamp head`
- **Datos Iniciales:**
  - Ejecuta el script `datosControlEquipos.sql` para poblar la base de datos con roles, permisos, y datos de ejemplo iniciales.

### Instalación de Dependencias

1. Crea un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate # Linux/macOS
   # venv\Scripts\activate # Windows
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

### Ejecución (Desarrollo)

1. Inicia el servidor Uvicorn con recarga automática:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8086
   ```

2. (Si usas Celery) Inicia el worker en otra terminal:
   ```bash
   celery -A app.worker worker --loglevel=info
   ```

### Ejecución (Docker - Recomendado)

1. Asegúrate de tener Docker y Docker Compose instalados.
2. Verifica que tu archivo `.env` está configurado.
3. Ejecuta:
   ```bash
   docker-compose up --build -d
   ```
   Esto levantará el backend, la base de datos, Redis y el worker de Celery.

4. Para detener:
   ```bash
   docker-compose down
   ```

---

## 📚 Documentación de la API

Una vez que la aplicación está corriendo, puedes acceder a la documentación interactiva de la API (generada automáticamente por FastAPI) en las siguientes URLs:

- **Swagger UI:** `http://localhost:8086/api/v1/docs`
- **ReDoc:** `http://localhost:8086/api/v1/redoc`

---

## 📁 Estructura del Proyecto

```
├── alembic/              # Migraciones de base de datos (Alembic)
├── app/                  # Directorio principal de la aplicación FastAPI
│   ├── api/              # Endpoints de la API, organizados por recurso
│   ├── core/             # Configuración, seguridad y lógica central
│   ├── db/               # Sesión de BD y modelos base
│   ├── models/           # Modelos ORM de SQLAlchemy
│   ├── schemas/          # Esquemas Pydantic para validación y serialización
│   ├── services/         # Lógica de negocio y acceso a datos
│   └── tasks/            # Tareas asíncronas de Celery
├── logs/                 # Archivos de log generados
├── scripts/              # Scripts de utilidad (ej. start.sh)
├── tests/                # Pruebas unitarias y de integración
├── uploads/              # Directorio para archivos subidos
├── .env.example          # Plantilla de variables de entorno
├── alembic.ini           # Configuración de Alembic
├── docker-compose.yml    # Orquestación de contenedores
├── Dockerfile            # Definición del contenedor de la aplicación
├── pytest.ini            # Configuración de Pytest
├── README.md             # Este archivo
└── requirements.txt      # Dependencias de Python
```

---

## 📝 TODO / Mejoras Futuras

- [ ] Implementar lógica real en tareas Celery (envío de emails, generación de reportes).
- [ ] Añadir pruebas unitarias y de integración más exhaustivas.
- [ ] Refinar el manejo de errores y el formato de los logs.
- [ ] Optimizar queries complejas si es necesario.
- [ ] Implementar la subida de archivos a un almacenamiento persistente (ej. S3, MinIO).
- [ ] Añadir mecanismos de caché (ej: Redis) para endpoints de lectura frecuente.
- [ ] Configurar un pipeline de CI/CD para despliegue automático.

---

## 🤝 Contribuciones

Las contribuciones son lo que hace a la comunidad de código abierto un lugar increíble para aprender, inspirar y crear. Cualquier contribución que hagas será **muy apreciada**.

1. Haz un Fork del Proyecto.
2. Crea tu Rama de Característica (`git checkout -b feature/AmazingFeature`).
3. Haz Commit de tus Cambios (`git commit -m 'feat: Add some AmazingFeature'`).
4. Haz Push a la Rama (`git push origin feature/AmazingFeature`).
5. Abre un Pull Request.

---

## 📄 Licencia

Distribuido bajo la Licencia MIT. Ver el archivo `LICENSE` para más información.

---

## 📧 Contacto

HabunoGD1809 - [https://github.com/HabunoGD1809](https://github.com/HabunoGD1809)

Enlace del Proyecto: [https://github.com/HabunoGD1809/control_equipos_backend](https://github.com/HabunoGD1809/control_equipos_backend)

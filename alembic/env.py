import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Añadimos la ruta del proyecto al path de Python
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Importamos la Base y TODOS los modelos de la aplicación
from app.db.base import Base
from app.models import *
from app.core.config import settings

# Obtenemos el objeto de configuración de Alembic
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Asignamos los metadatos y la URL de la base de datos
target_metadata = Base.metadata
config.set_main_option('sqlalchemy.url', str(settings.DATABASE_URI))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"param_style": "named"},
        version_table_schema=target_metadata.schema,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Nos aseguramos de que el esquema exista antes de continuar
        with connection.begin():
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_metadata.schema}"))

        # Configuramos el contexto de Alembic
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=target_metadata.schema,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

import logging
import traceback

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError # noqa
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound

# Importar errores específicos de psycopg si está disponible
try:
    # Usar psycopg en lugar de psycopg2 si es v3
    from psycopg import errors as psycopg_errors
    PSycopgError = psycopg_errors.Error
    PG_RaiseException = psycopg_errors.RaiseException
    PG_UniqueViolation = psycopg_errors.UniqueViolation
    PG_ForeignKeyViolation = psycopg_errors.ForeignKeyViolation
    PG_CheckViolation = psycopg_errors.CheckViolation
    PG_ExclusionViolation = psycopg_errors.ExclusionViolation
    PG_NotNullViolation = psycopg_errors.NotNullViolation
    # Códigos SQLSTATE específicos de psycopg
    PGCODE_UNIQUE_VIOLATION = getattr(psycopg_errors.UniqueViolation, 'sqlstate', "23505")
    PGCODE_FOREIGN_KEY_VIOLATION = getattr(psycopg_errors.ForeignKeyViolation, 'sqlstate', "23503")
    PGCODE_CHECK_VIOLATION = getattr(psycopg_errors.CheckViolation, 'sqlstate', "23514")
    PGCODE_EXCLUSION_VIOLATION = getattr(psycopg_errors.ExclusionViolation, 'sqlstate', "23P01")
    PGCODE_NOT_NULL_VIOLATION = getattr(psycopg_errors.NotNullViolation, 'sqlstate', "23502")
    PGCODE_RAISE_EXCEPTION = getattr(psycopg_errors.RaiseException, 'sqlstate', "P0001")
except ImportError:
    logging.warning("No se pudo importar psycopg. El manejo detallado de errores de DB puede ser limitado.")
    psycopg_errors = None # type: ignore
    PSycopgError = SQLAlchemyError # type: ignore
    PG_RaiseException = SQLAlchemyError # type: ignore
    PG_UniqueViolation = IntegrityError # type: ignore
    PG_ForeignKeyViolation = IntegrityError # type: ignore
    PG_CheckViolation = IntegrityError # type: ignore # Usar IntegrityError como fallback
    PG_ExclusionViolation = SQLAlchemyError # type: ignore # Usado para la instancia, el código PGCODE_ se mantiene
    PG_NotNullViolation = IntegrityError # type: ignore
    # Códigos SQLSTATE genéricos (menos fiables si psycopg no está)
    PGCODE_UNIQUE_VIOLATION = "23505"
    PGCODE_FOREIGN_KEY_VIOLATION = "23503"
    PGCODE_CHECK_VIOLATION = "23514"
    PGCODE_EXCLUSION_VIOLATION = "23P01"
    PGCODE_NOT_NULL_VIOLATION = "23502"
    PGCODE_RAISE_EXCEPTION = "P0001" # Usado para excepciones RAISE EXCEPTION en PL/pgSQL


logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: Exception):
    """
    Manejador para errores de validación de Pydantic en las solicitudes.
    """
    if not isinstance(exc, RequestValidationError):
        return await generic_exception_handler(request, exc)

    error_details = []
    for error in exc.errors():
        field_loc = error.get("loc", ["body"])
        if field_loc and field_loc[0] == 'body' and len(field_loc) > 1:
            field = " -> ".join(map(str, field_loc[1:]))
        elif field_loc and field_loc[0] != 'body':
            field = " -> ".join(map(str, field_loc))
        else:
            field = "body" if field_loc == ['body'] else " -> ".join(map(str, field_loc))
        message = error.get("msg", "Error de validación")
        error_details.append({"field": field, "message": message})
    log_message = f"Error de Validación en Request: {request.method} {request.url} - Errores: {error_details}"
    logger.warning(log_message)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Error de validación en los datos de entrada.", "errors": error_details},
    )

async def http_exception_handler(request: Request, exc: Exception):
    """
    Manejador para excepciones HTTP explícitas lanzadas en la aplicación.
    """
    if not isinstance(exc, HTTPException):
        return await generic_exception_handler(request, exc)

    log_message = f"HTTPException - Status: {exc.status_code}, Detail: {exc.detail}, Request: {request.method} {request.url}"
    if exc.status_code >= 500:
        logger.error(log_message, exc_info=False)
    elif exc.status_code >= 400:
        logger.warning(log_message)
    else:
        logger.info(log_message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

async def database_exception_handler(request: Request, exc: Exception):
    """
    Manejador para errores relacionados con la base de datos (SQLAlchemy y psycopg).
    """
    if not isinstance(exc, SQLAlchemyError):
        return await generic_exception_handler(request, exc)

    original_exc = getattr(exc, 'orig', None)
    pgcode = getattr(original_exc, 'pgcode', None)
    diag_message = None
    constraint_name = None
    error_message_for_matching = str(original_exc if original_exc else exc)

    if psycopg_errors and original_exc and hasattr(original_exc, 'diag'):
        diag_obj = getattr(original_exc, 'diag', None)
        if diag_obj:
             diag_message = getattr(diag_obj, 'message_primary', None)
             constraint_name = getattr(diag_obj, 'constraint_name', None)
        if diag_message:
            error_message_for_matching = diag_message

    logger.error(
        f"Database Error Handler - Type: {type(original_exc).__name__ if original_exc else type(exc).__name__}, "
        f"PGCode: {pgcode}, Constraint: '{constraint_name}', DiagMsg: '{diag_message}', MatchMsg: '{error_message_for_matching}', "
        f"Request: {request.method} {request.url}",
        exc_info=True
    )

    user_message = "Ocurrió un error interno del servidor al procesar la solicitud."
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return_response_directly = False

    if pgcode == PGCODE_CHECK_VIOLATION or \
       (isinstance(exc, IntegrityError) and "violates check constraint" in error_message_for_matching.lower()):
        logger.debug(f"DB Handler: Captured CheckViolation (PGCode:{pgcode}). Constraint: '{constraint_name}', MatchMsg: '{error_message_for_matching}'")
        if constraint_name == "check_numero_serie_format" or "violates check constraint \"check_numero_serie_format\"" in error_message_for_matching.lower():
             user_message = "El formato del número de serie no es válido."
             status_code = status.HTTP_400_BAD_REQUEST
        elif constraint_name == "reservas_equipo_fechas_check" or "violates check constraint \"reservas_equipo_fechas_check\"" in error_message_for_matching.lower():
            user_message = "La fecha de fin de la reserva no puede ser anterior o igual a la fecha de inicio."
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            user_message = f"Los datos proporcionados violan una regla de negocio (restricción: {constraint_name or 'desconocida'})."
            status_code = status.HTTP_400_BAD_REQUEST
        return_response_directly = True

    elif pgcode == PGCODE_UNIQUE_VIOLATION or isinstance(original_exc, PG_UniqueViolation) or \
         (isinstance(exc, IntegrityError) and ("unique constraint" in error_message_for_matching.lower() or "duplicate key value violates unique constraint" in error_message_for_matching.lower())):
         logger.debug(f"DB Handler: Captured UniqueViolation (PGCode:{pgcode}). Constraint: '{constraint_name}', MatchMsg: '{error_message_for_matching}'")
         detail_msg = getattr(getattr(original_exc, 'diag', {}), 'detail', None) if original_exc else error_message_for_matching
         if constraint_name == "uq_usuarios_nombre_usuario" or "usuarios_nombre_usuario_key" in error_message_for_matching.lower(): user_message = "Nombre de usuario ya registrado."
         elif constraint_name == "uq_usuarios_email" or "usuarios_email_key" in error_message_for_matching.lower(): user_message = "Correo electrónico ya registrado."
         elif constraint_name == "uq_equipos_numero_serie" or "equipos_numero_serie_key" in error_message_for_matching.lower(): user_message = "Número de serie ya registrado."
         elif constraint_name == "uq_equipos_codigo_interno" or "equipos_codigo_interno_key" in error_message_for_matching.lower(): user_message = "Código interno ya registrado."
         elif constraint_name == "uq_proveedores_nombre" or "proveedores_nombre_key" in error_message_for_matching.lower(): user_message = "Ya existe un proveedor con ese nombre."
         elif constraint_name == "uq_proveedores_rnc" or "proveedores_rnc_key" in error_message_for_matching.lower(): user_message = "Ya existe un proveedor con ese RNC."
         elif constraint_name == "uq_roles_nombre" or "roles_nombre_key" in error_message_for_matching.lower(): user_message = "Ya existe un rol con ese nombre."
         elif constraint_name == "uq_permisos_nombre" or "permisos_nombre_key" in error_message_for_matching.lower(): user_message = "Ya existe un permiso con ese nombre."
         elif constraint_name and "uq_estados_equipo_nombre" in constraint_name : user_message = "Ya existe un estado de equipo con ese nombre."
         elif detail_msg and ("is already present" in detail_msg or "ya existe" in detail_msg.lower()): user_message = f"Conflicto: {detail_msg}"
         else: user_message = f"Conflicto: Ya existe un registro con datos que deben ser únicos (restricción: {constraint_name or 'desconocida'})."
         status_code = status.HTTP_409_CONFLICT
         return_response_directly = True

    elif pgcode == PGCODE_FOREIGN_KEY_VIOLATION or isinstance(original_exc, PG_ForeignKeyViolation) or \
         (isinstance(exc, IntegrityError) and "foreign key constraint" in error_message_for_matching.lower()):
         logger.debug(f"DB Handler: Captured ForeignKeyViolation (PGCode:{pgcode}). Constraint: '{constraint_name}', MatchMsg: '{error_message_for_matching}'")
         detail_msg = getattr(getattr(original_exc, 'diag', {}), 'detail', None) if original_exc else error_message_for_matching
         if constraint_name == "fk_usuarios_rol": user_message = "El Rol especificado no fue encontrado."
         elif constraint_name == "fk_equipos_estado": user_message = "El Estado de Equipo especificado no fue encontrado."
         # ... (otros mapeos FK específicos) ...
         elif detail_msg and ("not present in table" in detail_msg or "no está presente en la tabla" in detail_msg.lower()): user_message = f"Error de referencia: {detail_msg}"
         else: user_message = f"Error de referencia: El registro vinculado no existe (restricción: {constraint_name or 'desconocida'})."
         status_code = status.HTTP_404_NOT_FOUND # O 422
         return_response_directly = True

    elif pgcode == PGCODE_EXCLUSION_VIOLATION or isinstance(original_exc, PG_ExclusionViolation) or \
         (isinstance(exc, IntegrityError) and "exclusion constraint" in error_message_for_matching.lower()):
         logger.debug(f"DB Handler: Captured ExclusionViolation (PGCode:{pgcode}). Constraint: '{constraint_name}', MatchMsg: '{error_message_for_matching}'")
         user_message = "Conflicto: Existe un solapamiento con un registro existente."
         if constraint_name == "reservas_equipo_equipo_id_tstzrange_excl":
             user_message = "La reserva se solapa con otra reserva existente para el mismo equipo en el rango de fechas especificado."
         elif constraint_name:
             user_message = f"Conflicto por restricción de exclusión '{constraint_name}': Existe un solapamiento con un registro existente."
         status_code = status.HTTP_409_CONFLICT
         return_response_directly = True

    elif pgcode == PGCODE_NOT_NULL_VIOLATION or isinstance(original_exc, PG_NotNullViolation) or \
         (isinstance(exc, IntegrityError) and "violates not-null constraint" in error_message_for_matching.lower()):
         logger.debug(f"DB Handler: Captured NotNullViolation (PGCode:{pgcode}). MatchMsg: '{error_message_for_matching}'")
         column_name = getattr(getattr(original_exc, 'diag', {}), 'column_name', 'desconocido') if original_exc else 'desconocido'
         user_message = f"Error de datos: El campo '{column_name}' no puede ser nulo."
         status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
         return_response_directly = True

    elif pgcode == PGCODE_RAISE_EXCEPTION or (psycopg_errors and isinstance(original_exc, PG_RaiseException)):
        logger.warning(f"DB Handler: Captured PG_RaiseException (PGCode:{pgcode}). Mensaje: '{error_message_for_matching}'")
        # Mapeos específicos para excepciones RAISE EXCEPTION de funciones PL/pgSQL
        if "stock insuficiente" in error_message_for_matching.lower():
            user_message = error_message_for_matching
            status_code = status.HTTP_409_CONFLICT
        elif "no se puede cancelar un movimiento en estado" in error_message_for_matching.lower():
            user_message = error_message_for_matching
            status_code = status.HTTP_409_CONFLICT
        # ... (otros mapeos de RAISE EXCEPTION) ...
        else:
            user_message = f"Error en lógica de base de datos: {error_message_for_matching}"
            status_code = status.HTTP_400_BAD_REQUEST
        return_response_directly = True

    elif isinstance(exc, IntegrityError): # Fallback genérico para IntegrityError
         logger.warning(f"DB Handler: Captured generic IntegrityError (no specific mapping hit). PGCode:{pgcode}, Constraint: '{constraint_name}', MatchMsg: '{error_message_for_matching}'")
         user_message = "Error de integridad en la base de datos. Verifique los datos."
         status_code = status.HTTP_409_CONFLICT
         return_response_directly = True
    elif isinstance(exc, NoResultFound):
        logger.warning(f"DB Handler: Recurso no encontrado (NoResultFound): {str(exc)}")
        user_message = "El recurso solicitado no fue encontrado."
        status_code = status.HTTP_404_NOT_FOUND
        return_response_directly = True

    if return_response_directly:
        logger.info(f"DB Handler: Mapeando error DB a -> Status={status_code}, Detail='{user_message}'")
        return JSONResponse(
            status_code=status_code,
            content={"detail": user_message},
        )
    elif isinstance(exc, HTTPException):
        logger.debug(f"DB Handler: Re-raising existing HTTPException: Status={exc.status_code}, Detail='{exc.detail}'")
        raise exc
    else:
        logger.error(f"DB Handler: Error DB no mapeado o inesperado resultando en 500. Exception: {type(exc).__name__} - {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Ocurrió un error interno del servidor al procesar la solicitud de base de datos."},
        )


async def generic_exception_handler(request: Request, exc: Exception):
    """
    Manejador genérico para cualquier excepción no capturada por otros manejadores.
    """
    log_message = f"Unhandled Python Exception: {type(exc).__name__} - {exc}, Request: {request.method} {request.url}\n{traceback.format_exc()}"
    logger.critical(log_message)
    user_message = "Ocurrió un error interno inesperado en la aplicación."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": user_message},
    )

def register_error_handlers(app: FastAPI):
    """Registra todos los manejadores de excepciones personalizados en la app FastAPI."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    logger.info("Manejadores de errores personalizados registrados.")

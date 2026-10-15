"""Initial release: full schema, database rules, views and essential catalogs.

Revision ID: f01d20261014
Revises: None
Create Date: 2026-10-14

Frozen from a migrated, verified PostgreSQL schema. Credentials and operational
records are intentionally absent; scripts/bootstrap.py creates the administrator.
The retired migration chain is preserved separately in the pre-delivery backup.
"""
from alembic import op
from sqlalchemy import text

revision = "f01d20261014"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_SQL = r"""
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: control_equipos; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS control_equipos;


--
-- Name: actualizar_busqueda_documento(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_busqueda_documento() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.titulo, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.descripcion, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre_archivo, '')), 'C');
        RETURN NEW;
    END;
    $$;


--
-- Name: actualizar_busqueda_equipo(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_busqueda_equipo() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_ubicacion_nombre TEXT := '';
        v_marca_nombre TEXT := '';
    BEGIN
        IF NEW.ubicacion_id IS NOT NULL THEN
            SELECT nombre INTO v_ubicacion_nombre FROM control_equipos.ubicaciones WHERE id = NEW.ubicacion_id;
        END IF;

        IF NEW.marca_id IS NOT NULL THEN
            SELECT nombre INTO v_marca_nombre FROM control_equipos.marcas WHERE id = NEW.marca_id;
        END IF;

        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(v_marca_nombre, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(v_ubicacion_nombre, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');

        RETURN NEW;
    END;
    $$;


--
-- Name: actualizar_busqueda_mantenimiento(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_busqueda_mantenimiento() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      DECLARE tecnico_nombre text;
      BEGIN
        SELECT nombre_completo INTO tecnico_nombre FROM control_equipos.tecnicos_mantenimiento WHERE id=NEW.tecnico_id;
        NEW.texto_busqueda = setweight(to_tsvector('spanish', COALESCE(tecnico_nombre, '')), 'B') || setweight(to_tsvector('spanish', COALESCE(NEW.observaciones, '')), 'C');
        RETURN NEW;
      END $$;


--
-- Name: actualizar_fecha_proximo_mantenimiento(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_fecha_proximo_mantenimiento() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE periodicidad integer; fecha_base timestamptz;
    BEGIN
      IF NEW.estado='Completado' THEN
        SELECT periodicidad_dias INTO periodicidad FROM control_equipos.tipos_mantenimiento WHERE id=NEW.tipo_mantenimiento_id AND es_preventivo;
        fecha_base := COALESCE(NEW.fecha_finalizacion, NEW.fecha_inicio, NEW.fecha_programada);
        NEW.fecha_proximo_mantenimiento := CASE WHEN periodicidad IS NOT NULL AND fecha_base IS NOT NULL THEN fecha_base + periodicidad * interval '1 day' ELSE NULL END;
      ELSE NEW.fecha_proximo_mantenimiento := NULL;
      END IF;
      RETURN NEW;
    END $$;


--
-- Name: actualizar_inventario_stock_fn(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_inventario_stock_fn() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE v_ubicacion uuid; v_lote text; v_updated integer;
    BEGIN
      IF NEW.cantidad <= 0 THEN RAISE EXCEPTION 'La cantidad debe ser positiva.'; END IF;
      IF NEW.tipo_movimiento IN ('Entrada Compra','Entrada Abastecimiento','Ajuste Positivo','Transferencia Entrada','Devolucion Interna') THEN
        v_ubicacion := NEW.ubicacion_destino_id;
        v_lote := COALESCE(NULLIF(trim(NEW.lote_destino),''),'N/A');
        IF v_ubicacion IS NULL THEN RAISE EXCEPTION 'Ubicación destino requerida.'; END IF;
        INSERT INTO control_equipos.inventario_stock (tipo_item_id,ubicacion_id,lote,cantidad_actual,costo_promedio_ponderado,ultima_actualizacion)
        VALUES (NEW.tipo_item_id,v_ubicacion,v_lote,NEW.cantidad,NEW.costo_unitario,NOW())
        ON CONFLICT (tipo_item_id,ubicacion_id,lote) DO UPDATE SET
          costo_promedio_ponderado = CASE WHEN NEW.costo_unitario IS NULL THEN control_equipos.inventario_stock.costo_promedio_ponderado
            WHEN control_equipos.inventario_stock.cantidad_actual = 0 THEN NEW.costo_unitario
            WHEN control_equipos.inventario_stock.costo_promedio_ponderado IS NULL THEN NULL
            ELSE (control_equipos.inventario_stock.cantidad_actual * control_equipos.inventario_stock.costo_promedio_ponderado + NEW.cantidad * NEW.costo_unitario)
                 / (control_equipos.inventario_stock.cantidad_actual + NEW.cantidad) END,
          cantidad_actual = control_equipos.inventario_stock.cantidad_actual + NEW.cantidad, ultima_actualizacion = NOW();
      ELSIF NEW.tipo_movimiento IN ('Salida Uso','Salida Descarte','Ajuste Negativo','Transferencia Salida','Devolucion Proveedor') THEN
        v_ubicacion := NEW.ubicacion_origen_id;
        v_lote := COALESCE(NULLIF(trim(NEW.lote_origen),''),'N/A');
        IF v_ubicacion IS NULL THEN RAISE EXCEPTION 'Ubicación origen requerida.'; END IF;
        UPDATE control_equipos.inventario_stock SET cantidad_actual = cantidad_actual - NEW.cantidad, ultima_actualizacion = NOW()
        WHERE tipo_item_id = NEW.tipo_item_id AND ubicacion_id = v_ubicacion AND lote = v_lote AND cantidad_actual >= NEW.cantidad;
        GET DIAGNOSTICS v_updated = ROW_COUNT;
        IF v_updated = 0 THEN RAISE EXCEPTION 'Stock insuficiente en la ubicación y lote seleccionados.'; END IF;
      ELSE RAISE EXCEPTION 'Tipo de movimiento de inventario inválido.';
      END IF;
      RETURN NEW;
    END; $$;


--
-- Name: actualizar_licencia_disponible_fn(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.actualizar_licencia_disponible_fn() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_licencia_id UUID;
        v_change INTEGER;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            v_licencia_id := NEW.licencia_id;
            v_change := -1;
        ELSIF TG_OP = 'DELETE' THEN
            v_licencia_id := OLD.licencia_id;
            v_change := 1;
        ELSE
            RETURN NEW;
        END IF;

        UPDATE control_equipos.licencias_software
        SET cantidad_disponible = cantidad_disponible + v_change,
            updated_at = NOW()
        WHERE id = v_licencia_id;

        IF (SELECT cantidad_disponible FROM control_equipos.licencias_software WHERE id = v_licencia_id) < 0 THEN
            RAISE EXCEPTION 'Error de consistencia: Cantidad disponible de licencia no puede ser negativa (Licencia ID: %)', v_licencia_id;
        END IF;

        IF TG_OP = 'INSERT' THEN RETURN NEW; ELSE RETURN OLD; END IF;
    END;
    $$;


--
-- Name: audit_trigger_fn(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.audit_trigger_fn() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            actor uuid;
            old_value jsonb;
            new_value jsonb;
            private_keys text[] := ARRAY['contrasena','hashed_password','password','token_temporal','token_hash','clave_producto','refresh_token','access_token'];
        BEGIN
            actor := nullif(current_setting('myapp.current_user_id', true),'')::uuid;
            IF TG_OP <> 'INSERT' THEN old_value := to_jsonb(OLD)-private_keys; END IF;
            IF TG_OP <> 'DELETE' THEN new_value := to_jsonb(NEW)-private_keys; END IF;
            IF TG_OP <> 'UPDATE' OR OLD IS DISTINCT FROM NEW THEN
                INSERT INTO control_equipos.audit_log(table_name,operation,old_data,new_data,username,app_user_id)
                VALUES (TG_TABLE_NAME,TG_OP,old_value,new_value,session_user,actor);
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;


--
-- Name: buscar_equipos(text); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.buscar_equipos(query_term text) RETURNS TABLE(id uuid, nombre character varying, numero_serie character varying, marca_id uuid, modelo character varying, ubicacion_actual character varying, estado_nombre character varying, relevancia double precision)
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT e.id,
               CAST(e.nombre AS character varying),
               CAST(e.numero_serie AS character varying),
               e.marca_id,
               CAST(e.modelo AS character varying),
               CAST(u.nombre AS character varying) AS ubicacion_actual,
               CAST(ee.nombre AS character varying) AS estado_nombre,
               CAST(ts_rank_cd(e.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        WHERE e.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, e.nombre ASC;
    END;
    $$;


--
-- Name: busqueda_global(text); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.busqueda_global(query_term text) RETURNS TABLE(tipo text, id uuid, titulo text, descripcion text, relevancia double precision, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY

        -- 1. BÚSQUEDA EN EQUIPOS
        SELECT
            CAST('equipo' AS text) AS tipo,
            e.id,
            CAST(e.nombre AS text) AS titulo,
            CAST('Serie: ' || e.numero_serie || ' | Marca: ' || COALESCE(m_marca.nombre, 'N/A') || ' | Modelo: ' || COALESCE(e.modelo, 'N/A') AS text) AS descripcion,
            CAST(ts_rank_cd(e.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia,
            jsonb_build_object(
                'numero_serie', e.numero_serie,
                'marca', m_marca.nombre,
                'modelo', e.modelo,
                'ubicacion', u.nombre,
                'estado_id', e.estado_id
            ) AS metadata
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        LEFT JOIN control_equipos.marcas m_marca ON e.marca_id = m_marca.id
        WHERE e.texto_busqueda @@ plainto_tsquery('spanish', query_term)

        UNION ALL

        -- 2. BÚSQUEDA EN DOCUMENTOS
        SELECT
            CAST('documento' AS text) AS tipo,
            d.id,
            CAST(d.titulo AS text) AS titulo,
            CAST(COALESCE(d.descripcion, 'Sin descripción') AS text) AS descripcion,
            CAST(ts_rank_cd(d.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia,
            jsonb_build_object(
                'equipo_id', d.equipo_id,
                'tipo_documento_id', d.tipo_documento_id,
                'nombre_archivo', d.nombre_archivo,
                'enlace', d.enlace
            ) AS metadata
        FROM control_equipos.documentacion d
        WHERE d.texto_busqueda @@ plainto_tsquery('spanish', query_term)

        UNION ALL

        -- 3. BÚSQUEDA EN MANTENIMIENTOS (AQUÍ ESTÁ LA CORRECCIÓN: tecnico_id)
        SELECT
            CAST('mantenimiento' AS text) AS tipo,
            mt.id,
            CAST('Mantenimiento ID: ' || mt.id::TEXT AS text) AS titulo,
            CAST('Técnico ID: ' || COALESCE(mt.tecnico_id::text, 'N/A') || ' | Obs: ' || COALESCE(mt.observaciones, 'N/A') AS text) AS descripcion,
            CAST(ts_rank_cd(mt.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia,
            jsonb_build_object(
                'equipo_id', mt.equipo_id,
                'tipo_mantenimiento_id', mt.tipo_mantenimiento_id,
                'tecnico', mt.tecnico_id,
                'fecha_programada', mt.fecha_programada,
                'estado', mt.estado
            ) AS metadata
        FROM control_equipos.mantenimiento mt
        WHERE mt.texto_busqueda @@ plainto_tsquery('spanish', query_term)

        ORDER BY relevancia DESC, tipo ASC, titulo ASC;
    END;
    $$;


--
-- Name: gestionar_particiones_audit_log(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.gestionar_particiones_audit_log() RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_current_partition_name TEXT;
        v_next_partition_name TEXT;
        v_from_date_current TEXT;
        v_to_date_current TEXT;
        v_from_date_next TEXT;
        v_to_date_next TEXT;
    BEGIN
        v_from_date_current := to_char(NOW(), 'YYYY-MM-01');
        v_to_date_current := to_char(NOW() + INTERVAL '1 month', 'YYYY-MM-01');
        v_current_partition_name := 'audit_log_y' || to_char(NOW(), 'YYYY') || 'm' || to_char(NOW(), 'MM');
        IF NOT EXISTS (SELECT FROM pg_class WHERE relname = v_current_partition_name) THEN
            EXECUTE format(
                'CREATE TABLE control_equipos.%I PARTITION OF control_equipos.audit_log FOR VALUES FROM (%L) TO (%L);',
                v_current_partition_name, v_from_date_current, v_to_date_current
            );
        END IF;
        v_from_date_next := to_char(NOW() + INTERVAL '1 month', 'YYYY-MM-01');
        v_to_date_next := to_char(NOW() + INTERVAL '2 months', 'YYYY-MM-01');
        v_next_partition_name := 'audit_log_y' || to_char(NOW() + INTERVAL '1 month', 'YYYY') || 'm' || to_char(NOW() + INTERVAL '1 month', 'MM');
        IF NOT EXISTS (SELECT FROM pg_class WHERE relname = v_next_partition_name) THEN
            EXECUTE format(
                'CREATE TABLE control_equipos.%I PARTITION OF control_equipos.audit_log FOR VALUES FROM (%L) TO (%L);',
                v_next_partition_name, v_from_date_next, v_to_date_next
            );
        END IF;
    END;
    $$;


--
-- Name: notificar_cambio_notificacion(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.notificar_cambio_notificacion() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        PERFORM pg_notify('control_equipos_notificaciones', OLD.usuario_id::text);
        RETURN OLD;
      END IF;
      PERFORM pg_notify('control_equipos_notificaciones', NEW.usuario_id::text);
      IF TG_OP = 'UPDATE' AND OLD.usuario_id IS DISTINCT FROM NEW.usuario_id THEN
        PERFORM pg_notify('control_equipos_notificaciones', OLD.usuario_id::text);
      END IF;
      RETURN NEW;
    END; $$;


--
-- Name: proteger_claves_stock(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.proteger_claves_stock() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      IF (NEW.tipo_item_id, NEW.ubicacion_id, NEW.lote) IS DISTINCT FROM (OLD.tipo_item_id, OLD.ubicacion_id, OLD.lote) THEN
        RAISE EXCEPTION 'La ubicación y el lote del stock se corrigen mediante movimientos de transferencia.';
      END IF;
      RETURN NEW;
    END; $$;


--
-- Name: proteger_ledger_inventario(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.proteger_ledger_inventario() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF TG_OP='DELETE' OR (to_jsonb(NEW)-ARRAY['notas','referencia_externa']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['notas','referencia_externa']) THEN
                RAISE EXCEPTION 'El historial de inventario es inmutable. Registre un movimiento de ajuste para corregir existencias.';
            END IF;
            RETURN NEW;
        END $$;


--
-- Name: refresh_materialized_views(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.refresh_materialized_views() RETURNS void
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RAISE NOTICE 'Refrescando vista materializada: mv_equipos_estado...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY control_equipos.mv_equipos_estado;

        RAISE NOTICE 'Refrescando vista materializada: mv_mantenimientos_proximos...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY control_equipos.mv_mantenimientos_proximos;

        RAISE NOTICE 'Vistas materializadas refrescadas exitosamente.';
    END;
    $$;


--
-- Name: registrar_movimiento_equipo(uuid, uuid, text, uuid, uuid, text, timestamp with time zone, text, text, uuid); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.registrar_movimiento_equipo(p_equipo_id uuid, p_usuario_id uuid, p_tipo_movimiento text, p_ubicacion_origen_id uuid DEFAULT NULL::uuid, p_ubicacion_destino_id uuid DEFAULT NULL::uuid, p_proposito text DEFAULT NULL::text, p_fecha_prevista_retorno timestamp with time zone DEFAULT NULL::timestamp with time zone, p_recibido_por text DEFAULT NULL::text, p_observaciones text DEFAULT NULL::text, p_autorizado_por uuid DEFAULT NULL::uuid) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_movimiento_id UUID;
        v_estado_equipo RECORD;
        v_estado_final_id UUID;
        v_ubicacion_final_id UUID;
        v_current_user_has_auth_perm BOOLEAN;
        v_estado_mov_inicial TEXT := 'Completado';
    BEGIN
        SELECT ee.codigo, ee.nombre, ee.permite_movimientos, ee.requiere_autorizacion, e.ubicacion_id, e.estado_id, e.empleado_asignado_id
        INTO v_estado_equipo
        FROM control_equipos.equipos e
        JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        WHERE e.id = p_equipo_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Equipo no encontrado (ID: %)', p_equipo_id;
        END IF;

        IF EXISTS (SELECT 1 FROM control_equipos.movimientos WHERE equipo_id=p_equipo_id
            AND (estado IN ('Pendiente','Autorizado','En Proceso') OR (tipo_movimiento='Salida Temporal' AND estado='Completado' AND fecha_retorno IS NULL)) AND NOT (p_tipo_movimiento='Entrada' AND tipo_movimiento='Salida Temporal')) THEN
            RAISE EXCEPTION 'El equipo tiene un movimiento pendiente de recepción o autorización.';
        END IF;
        IF EXISTS (SELECT 1 FROM control_equipos.reservas_equipo WHERE equipo_id=p_equipo_id AND estado='En Curso') THEN
            RAISE EXCEPTION 'El equipo tiene una reserva en curso; registre su devolución primero.';
        END IF;
        IF EXISTS (SELECT 1 FROM control_equipos.mantenimiento WHERE equipo_id=p_equipo_id AND estado IN ('En Proceso','Pausado','Requiere Piezas')) THEN RAISE EXCEPTION 'El equipo tiene un mantenimiento en curso.'; END IF;
        IF p_ubicacion_origen_id IS NOT NULL AND p_tipo_movimiento<>'Entrada' AND p_ubicacion_origen_id IS DISTINCT FROM v_estado_equipo.ubicacion_id THEN
            RAISE EXCEPTION 'La ubicación origen no coincide con la ubicación actual del equipo.';
        END IF;
        IF p_ubicacion_destino_id IS NULL THEN RAISE EXCEPTION 'La ubicación destino es obligatoria.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM control_equipos.ubicaciones WHERE id=p_ubicacion_destino_id AND is_active) THEN
            RAISE EXCEPTION 'La ubicación destino debe estar activa.';
        END IF;
        IF NOT v_estado_equipo.permite_movimientos THEN
            RAISE EXCEPTION 'El equipo con estado "%" no permite movimientos actualmente.', v_estado_equipo.nombre;
        END IF;

        IF v_estado_equipo.requiere_autorizacion THEN


            SELECT EXISTS (
                SELECT 1 FROM control_equipos.usuarios u
                JOIN control_equipos.roles r ON u.rol_id = r.id
                JOIN control_equipos.roles_permisos rp ON r.id = rp.rol_id
                JOIN control_equipos.permisos p ON rp.permiso_id = p.id
                WHERE u.id = p_autorizado_por AND p.nombre = 'autorizar_movimientos'
            ) INTO v_current_user_has_auth_perm;

            IF p_autorizado_por IS NOT NULL AND NOT v_current_user_has_auth_perm THEN
                RAISE EXCEPTION 'El usuario que autoriza no tiene el permiso ''autorizar_movimientos''.';
            END IF;
        END IF;

        IF p_tipo_movimiento = 'Asignacion Interna' AND v_estado_equipo.codigo IS DISTINCT FROM 'disponible' THEN
            RAISE EXCEPTION 'Solo se pueden asignar equipos que están en estado "Disponible". Estado actual: "%".', v_estado_equipo.nombre;
        END IF;

        CASE p_tipo_movimiento
            WHEN 'Salida Temporal' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE codigo = 'prestado';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';

            WHEN 'Salida Definitiva' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE codigo = 'dado_de_baja';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);

            WHEN 'Entrada' THEN
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE codigo = 'disponible';
                v_ubicacion_final_id := p_ubicacion_destino_id;

            WHEN 'Asignacion Interna' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE codigo = 'en_uso';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';

            WHEN 'Transferencia Bodega' THEN
                v_estado_final_id := v_estado_equipo.estado_id;
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';
            ELSE
                RAISE EXCEPTION 'Tipo de movimiento no válido: %', p_tipo_movimiento;
        END CASE;

        IF v_estado_final_id IS NULL THEN RAISE EXCEPTION 'Falta el estado de destino del catálogo. Ejecute bootstrap.'; END IF;
        IF v_estado_equipo.requiere_autorizacion AND p_autorizado_por IS NULL THEN v_estado_mov_inicial := 'Pendiente'; END IF;
        INSERT INTO control_equipos.movimientos (estado_origen_id, empleado_origen_id, equipo_id, usuario_id, tipo_movimiento, ubicacion_origen_id, ubicacion_destino_id, proposito, fecha_prevista_retorno, recibido_por, observaciones, autorizado_por, estado)
        VALUES (v_estado_equipo.estado_id, v_estado_equipo.empleado_asignado_id, p_equipo_id, p_usuario_id, p_tipo_movimiento, p_ubicacion_origen_id, p_ubicacion_destino_id, p_proposito, p_fecha_prevista_retorno, p_recibido_por, p_observaciones, p_autorizado_por, v_estado_mov_inicial)
        RETURNING id INTO v_movimiento_id;

        IF v_estado_mov_inicial <> 'Pendiente' THEN
            UPDATE control_equipos.equipos SET estado_id=v_estado_final_id, ubicacion_id=v_ubicacion_final_id, updated_at=NOW() WHERE id=p_equipo_id;
        END IF;
        IF p_tipo_movimiento='Entrada' AND v_estado_mov_inicial<>'Pendiente' THEN
            UPDATE control_equipos.movimientos SET fecha_retorno=NOW(),estado='Completado'
            WHERE equipo_id=p_equipo_id AND tipo_movimiento='Salida Temporal' AND fecha_retorno IS NULL AND estado NOT IN ('Cancelado','Rechazado','Pendiente');
            UPDATE control_equipos.equipos SET empleado_asignado_id=NULL WHERE id=p_equipo_id;
        END IF;
        IF p_tipo_movimiento='Salida Definitiva' AND v_estado_mov_inicial<>'Pendiente' THEN
            UPDATE control_equipos.equipos SET empleado_asignado_id=NULL WHERE id=p_equipo_id;
        END IF;

        RETURN v_movimiento_id;
    END;
    $$;


--
-- Name: set_audit_user(uuid); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.set_audit_user(p_user_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
    BEGIN
        EXECUTE format('SET LOCAL myapp.current_user_id = %L', p_user_id::text);
    EXCEPTION
        WHEN OTHERS THEN
            RAISE EXCEPTION '[SET_AUDIT_USER] - FALLO CRÍTICO al establecer el usuario para auditoría: %. La transacción será revertida.', SQLERRM;
    END;
    $$;


--
-- Name: update_updated_at(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.update_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.updated_at := NOW();
        RETURN NEW;
    END;
    $$;


--
-- Name: validar_transferencia_inventario(); Type: FUNCTION; Schema: control_equipos; Owner: -
--

CREATE FUNCTION control_equipos.validar_transferencia_inventario() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE v_count integer; v_qty integer; v_items integer; v_salidas integer; v_entradas integer;
    BEGIN
      IF NEW.tipo_movimiento NOT IN ('Transferencia Entrada','Transferencia Salida') THEN RETURN NEW; END IF;
      IF NEW.referencia_transferencia IS NULL THEN RAISE EXCEPTION 'La transferencia requiere una referencia común.'; END IF;
      SELECT count(*),count(DISTINCT cantidad),count(DISTINCT tipo_item_id),
             count(*) FILTER (WHERE tipo_movimiento='Transferencia Salida'),count(*) FILTER (WHERE tipo_movimiento='Transferencia Entrada')
      INTO v_count,v_qty,v_items,v_salidas,v_entradas FROM control_equipos.inventario_movimientos
      WHERE referencia_transferencia=NEW.referencia_transferencia;
      IF v_count<>2 OR v_qty<>1 OR v_items<>1 OR v_salidas<>1 OR v_entradas<>1 THEN
         RAISE EXCEPTION 'Una transferencia debe registrar su salida y entrada en la misma transacción.';
      END IF;
      RETURN NEW;
    END; $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: asignaciones_licencia; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.asignaciones_licencia (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    licencia_id uuid NOT NULL,
    equipo_id uuid,
    usuario_id uuid,
    fecha_asignacion timestamp with time zone DEFAULT now(),
    instalado boolean DEFAULT true,
    notas text,
    CONSTRAINT ck_asignaciones_licencia_check_asignacion_exclusiva CHECK ((NOT ((equipo_id IS NOT NULL) AND (usuario_id IS NOT NULL)))),
    CONSTRAINT ck_asignaciones_licencia_check_asignacion_target CHECK (((equipo_id IS NOT NULL) OR (usuario_id IS NOT NULL)))
);


--
-- Name: audit_log; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    audit_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    table_name text NOT NULL,
    operation text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    username text DEFAULT CURRENT_USER,
    app_user_id uuid
)
PARTITION BY RANGE (audit_timestamp);


--
-- Name: audit_log_y2026m10; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.audit_log_y2026m10 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    audit_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    table_name text NOT NULL,
    operation text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    username text DEFAULT CURRENT_USER,
    app_user_id uuid
);


--
-- Name: audit_log_y2026m11; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.audit_log_y2026m11 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    audit_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    table_name text NOT NULL,
    operation text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    username text DEFAULT CURRENT_USER,
    app_user_id uuid
);


--
-- Name: backup_logs; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.backup_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    backup_timestamp timestamp with time zone DEFAULT now(),
    backup_status text,
    backup_type text,
    duration interval,
    file_path text,
    error_message text,
    notes text
);


--
-- Name: configuracion_empresa; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.configuracion_empresa (
    id integer NOT NULL,
    nombre character varying(150) DEFAULT 'ControlEquipos'::character varying NOT NULL,
    identificacion character varying(50),
    direccion text,
    telefono character varying(50),
    email character varying(254),
    logo_path character varying(255),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_configuracion_empresa_singleton_empresa CHECK ((id = 1))
);


--
-- Name: configuracion_empresa_id_seq; Type: SEQUENCE; Schema: control_equipos; Owner: -
--

CREATE SEQUENCE control_equipos.configuracion_empresa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: configuracion_empresa_id_seq; Type: SEQUENCE OWNED BY; Schema: control_equipos; Owner: -
--

ALTER SEQUENCE control_equipos.configuracion_empresa_id_seq OWNED BY control_equipos.configuracion_empresa.id;


--
-- Name: departamentos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.departamentos (
    id uuid NOT NULL,
    nombre character varying(150) NOT NULL,
    descripcion text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: documentacion; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.documentacion (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    equipo_id uuid,
    mantenimiento_id uuid,
    licencia_id uuid,
    tipo_documento_id uuid NOT NULL,
    titulo text NOT NULL,
    descripcion text,
    enlace text NOT NULL,
    nombre_archivo text,
    mime_type text,
    tamano_bytes bigint,
    fecha_subida timestamp with time zone DEFAULT now(),
    subido_por uuid,
    estado text DEFAULT 'Pendiente'::text,
    verificado_por uuid,
    fecha_verificacion timestamp with time zone,
    notas_verificacion text,
    texto_busqueda tsvector,
    CONSTRAINT ck_documentacion_documentacion_estado_check CHECK ((estado = ANY (ARRAY['Pendiente'::text, 'Verificado'::text, 'Rechazado'::text])))
);


--
-- Name: empleados; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.empleados (
    id uuid NOT NULL,
    nombre_completo character varying(255) NOT NULL,
    cargo character varying(150),
    email_corporativo character varying(255),
    departamento_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: equipo_componentes; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.equipo_componentes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    equipo_padre_id uuid NOT NULL,
    equipo_componente_id uuid NOT NULL,
    tipo_relacion text DEFAULT 'componente'::text,
    cantidad integer DEFAULT 1 NOT NULL,
    notas text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT ck_equipo_componentes_check_no_self_component CHECK ((equipo_padre_id <> equipo_componente_id)),
    CONSTRAINT ck_equipo_componentes_equipo_componentes_cantidad_check CHECK ((cantidad > 0)),
    CONSTRAINT ck_equipo_componentes_equipo_componentes_tipo_relacion_check CHECK ((tipo_relacion = ANY (ARRAY['componente'::text, 'conectado_a'::text, 'parte_de'::text, 'accesorio'::text])))
);


--
-- Name: equipos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.equipos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    numero_serie text NOT NULL,
    codigo_interno text,
    estado_id uuid NOT NULL,
    modelo text,
    fecha_adquisicion date,
    fecha_puesta_marcha date,
    fecha_garantia_expiracion date,
    valor_adquisicion numeric(12,2),
    proveedor_id uuid,
    centro_costo text,
    notas text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    texto_busqueda tsvector,
    ubicacion_id uuid,
    marca_id uuid,
    empleado_asignado_id uuid,
    tipo_activo character varying(30) DEFAULT 'Equipo'::character varying NOT NULL,
    especificaciones_tecnicas jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT check_numero_serie_format CHECK ((numero_serie ~ '^[A-Za-z0-9][A-Za-z0-9._/ :+\-]{0,99}$'::text)),
    CONSTRAINT ck_equipos_check_fecha_adq CHECK (((fecha_adquisicion IS NULL) OR (fecha_adquisicion <= CURRENT_DATE))),
    CONSTRAINT ck_equipos_check_fechas_logicas CHECK (((fecha_puesta_marcha IS NULL) OR (fecha_adquisicion IS NULL) OR (fecha_puesta_marcha >= fecha_adquisicion))),
    CONSTRAINT ck_equipos_check_valor_adq CHECK (((valor_adquisicion IS NULL) OR (valor_adquisicion >= (0)::numeric))),
    CONSTRAINT ck_equipos_equipo_ficha_objeto CHECK ((jsonb_typeof(especificaciones_tecnicas) = 'object'::text)),
    CONSTRAINT ck_equipos_equipo_tipo_activo_valido CHECK (((tipo_activo)::text = ANY ((ARRAY['Equipo'::character varying, 'Servidor'::character varying, 'Red'::character varying, 'Impresora'::character varying, 'UPS'::character varying, 'Almacenamiento'::character varying, 'Periférico'::character varying, 'Otro'::character varying])::text[])))
);


--
-- Name: estados_equipo; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.estados_equipo (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    permite_movimientos boolean DEFAULT true,
    requiere_autorizacion boolean DEFAULT false,
    es_estado_final boolean DEFAULT false,
    color_hex text,
    icono text,
    created_at timestamp with time zone DEFAULT now(),
    codigo character varying(32)
);


--
-- Name: inventario_movimientos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.inventario_movimientos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tipo_item_id uuid NOT NULL,
    tipo_movimiento text NOT NULL,
    cantidad integer NOT NULL,
    lote_origen text DEFAULT 'N/A'::text,
    lote_destino text DEFAULT 'N/A'::text,
    equipo_asociado_id uuid,
    mantenimiento_id uuid,
    usuario_id uuid,
    fecha_hora timestamp with time zone DEFAULT now(),
    costo_unitario numeric(12,4),
    motivo_ajuste text,
    referencia_externa text,
    referencia_transferencia uuid,
    notas text,
    ubicacion_origen_id uuid,
    ubicacion_destino_id uuid,
    procedencia character varying(150),
    entregado_por character varying(150),
    CONSTRAINT ck_inventario_movimientos_abastecimiento_documentado CHECK (((tipo_movimiento <> 'Entrada Abastecimiento'::text) OR ((NULLIF(TRIM(BOTH FROM procedencia), ''::text) IS NOT NULL) AND (NULLIF(TRIM(BOTH FROM referencia_externa), ''::text) IS NOT NULL)))),
    CONSTRAINT ck_inventario_movimientos_inventario_movimientos_cantidad_check CHECK ((cantidad > 0)),
    CONSTRAINT ck_inventario_movimientos_inventario_movimientos_tipo_m_b5ea CHECK ((tipo_movimiento = ANY (ARRAY['Entrada Compra'::text, 'Salida Uso'::text, 'Salida Descarte'::text, 'Ajuste Positivo'::text, 'Ajuste Negativo'::text, 'Transferencia Salida'::text, 'Transferencia Entrada'::text, 'Devolucion Proveedor'::text, 'Devolucion Interna'::text, 'Entrada Abastecimiento'::text])))
);


--
-- Name: inventario_stock; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.inventario_stock (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tipo_item_id uuid NOT NULL,
    lote text DEFAULT 'N/A'::text NOT NULL,
    fecha_caducidad date,
    cantidad_actual integer DEFAULT 0 NOT NULL,
    costo_promedio_ponderado numeric(12,4),
    ultima_actualizacion timestamp with time zone DEFAULT now(),
    ubicacion_id uuid,
    CONSTRAINT ck_inventario_stock_inventario_stock_cantidad_actual_check CHECK ((cantidad_actual >= 0)),
    CONSTRAINT stock_no_negativo CHECK ((cantidad_actual >= 0))
);


--
-- Name: licencias_software; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.licencias_software (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    software_catalogo_id uuid NOT NULL,
    clave_producto text,
    fecha_adquisicion date NOT NULL,
    fecha_expiracion date,
    proveedor_id uuid,
    costo_adquisicion numeric(12,2),
    numero_orden_compra text,
    cantidad_total integer DEFAULT 1 NOT NULL,
    cantidad_disponible integer DEFAULT 1 NOT NULL,
    notas text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT ck_licencias_software_check_disponible_no_mayor_total CHECK ((cantidad_disponible <= cantidad_total)),
    CONSTRAINT ck_licencias_software_check_expiracion_logica CHECK (((fecha_expiracion IS NULL) OR (fecha_adquisicion IS NULL) OR (fecha_expiracion > fecha_adquisicion)))
);


--
-- Name: login_logs; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.login_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid,
    nombre_usuario_intento text,
    intento timestamp with time zone DEFAULT now(),
    exito boolean,
    ip_origen text,
    user_agent text,
    motivo_fallo text
);


--
-- Name: mantenimiento; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.mantenimiento (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    equipo_id uuid NOT NULL,
    tipo_mantenimiento_id uuid NOT NULL,
    fecha_programada timestamp with time zone,
    fecha_inicio timestamp with time zone,
    fecha_finalizacion timestamp with time zone,
    fecha_proximo_mantenimiento timestamp with time zone,
    costo_estimado numeric(12,2),
    costo_real numeric(12,2),
    estado text DEFAULT 'Programado'::text,
    prioridad integer DEFAULT 0,
    observaciones text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    texto_busqueda tsvector,
    tecnico_id uuid NOT NULL,
    estado_equipo_anterior_id uuid,
    componentes_origen jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT ck_mantenimiento_mantenimiento_costo_real_check CHECK (((costo_real IS NULL) OR (costo_real >= (0)::numeric))),
    CONSTRAINT ck_mantenimiento_mantenimiento_estado_check CHECK ((estado = ANY (ARRAY['Programado'::text, 'En Proceso'::text, 'Completado'::text, 'Cancelado'::text, 'Pendiente Aprobacion'::text, 'Requiere Piezas'::text, 'Pausado'::text])))
);


--
-- Name: marcas; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.marcas (
    id uuid NOT NULL,
    nombre character varying(100) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: movimientos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.movimientos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    equipo_id uuid NOT NULL,
    usuario_id uuid,
    tipo_movimiento text NOT NULL,
    fecha_hora timestamp with time zone DEFAULT now(),
    fecha_prevista_retorno timestamp with time zone,
    fecha_retorno timestamp with time zone,
    proposito text,
    autorizado_por uuid,
    recibido_por text,
    observaciones text,
    estado text DEFAULT 'Completado'::text,
    created_at timestamp with time zone DEFAULT now(),
    ip_origen character varying(100),
    user_agent text,
    ubicacion_origen_id uuid,
    ubicacion_destino_id uuid,
    empleado_destino_id uuid,
    estado_origen_id uuid,
    empleado_origen_id uuid,
    componentes_origen jsonb DEFAULT '{}'::jsonb NOT NULL,
    empleado_receptor_id uuid,
    confirmado_por_id uuid,
    fecha_recepcion timestamp with time zone,
    entidad_receptora character varying(255),
    CONSTRAINT ck_movimientos_check_retorno_salida_temporal CHECK ((((tipo_movimiento = 'Salida Temporal'::text) AND (fecha_prevista_retorno IS NOT NULL)) OR (tipo_movimiento <> 'Salida Temporal'::text))),
    CONSTRAINT ck_movimientos_ck_movimientos_check_origen_destino_asignacion CHECK (((tipo_movimiento !~~ '%%Asignacion%%'::text) OR ((ubicacion_origen_id IS NOT NULL) AND (ubicacion_destino_id IS NOT NULL)))),
    CONSTRAINT ck_movimientos_movimientos_estado_check CHECK ((estado = ANY (ARRAY['Pendiente'::text, 'Autorizado'::text, 'En Proceso'::text, 'Completado'::text, 'Cancelado'::text, 'Rechazado'::text]))),
    CONSTRAINT ck_movimientos_movimientos_tipo_movimiento_check CHECK ((tipo_movimiento = ANY (ARRAY['Salida Temporal'::text, 'Salida Definitiva'::text, 'Entrada'::text, 'Asignacion Interna'::text, 'Transferencia Bodega'::text])))
);


--
-- Name: mv_equipos_estado; Type: MATERIALIZED VIEW; Schema: control_equipos; Owner: -
--

CREATE MATERIALIZED VIEW control_equipos.mv_equipos_estado AS
 SELECT ee.id AS estado_id,
    ee.nombre AS estado_nombre,
    ee.color_hex AS estado_color,
    count(e.id) AS cantidad_equipos,
    sum(
        CASE
            WHEN ee.permite_movimientos THEN 1
            ELSE 0
        END) AS cantidad_movibles,
    array_agg(e.id ORDER BY e.nombre) AS equipos_ids,
    array_agg(e.nombre ORDER BY e.nombre) AS equipos_nombres
   FROM (control_equipos.estados_equipo ee
     LEFT JOIN control_equipos.equipos e ON ((e.estado_id = ee.id)))
  GROUP BY ee.id, ee.nombre, ee.color_hex
  ORDER BY ee.nombre
  WITH NO DATA;


--
-- Name: tipos_mantenimiento; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.tipos_mantenimiento (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    periodicidad_dias integer,
    requiere_documentacion boolean DEFAULT false,
    es_preventivo boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT ck_tipos_mantenimiento_tipos_mantenimiento_periodicidad_4d34 CHECK (((periodicidad_dias IS NULL) OR (periodicidad_dias > 0)))
);


--
-- Name: ubicaciones; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.ubicaciones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    edificio text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    departamento_id uuid
);


--
-- Name: mv_mantenimientos_proximos; Type: MATERIALIZED VIEW; Schema: control_equipos; Owner: -
--

CREATE MATERIALIZED VIEW control_equipos.mv_mantenimientos_proximos AS
 SELECT m.id AS mantenimiento_id,
    m.equipo_id,
    e.nombre AS equipo_nombre,
    e.numero_serie AS equipo_serie,
    u.nombre AS equipo_ubicacion,
    tm.nombre AS tipo_mantenimiento_nombre,
    m.fecha_proximo_mantenimiento,
    m.estado AS mantenimiento_estado,
    ((m.fecha_proximo_mantenimiento)::date - CURRENT_DATE) AS dias_restantes
   FROM (((control_equipos.mantenimiento m
     JOIN control_equipos.equipos e ON ((m.equipo_id = e.id)))
     JOIN control_equipos.tipos_mantenimiento tm ON ((m.tipo_mantenimiento_id = tm.id)))
     LEFT JOIN control_equipos.ubicaciones u ON ((e.ubicacion_id = u.id)))
  WHERE ((m.fecha_proximo_mantenimiento IS NOT NULL) AND (m.fecha_proximo_mantenimiento >= now()) AND (m.fecha_proximo_mantenimiento <= (now() + '30 days'::interval)) AND (m.estado <> ALL (ARRAY['Completado'::text, 'Cancelado'::text])))
  ORDER BY m.fecha_proximo_mantenimiento
  WITH NO DATA;


--
-- Name: notificaciones; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.notificaciones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid NOT NULL,
    mensaje text NOT NULL,
    leido boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    fecha_leido timestamp with time zone,
    tipo text,
    urgencia integer DEFAULT 0,
    referencia_id uuid,
    referencia_tabla text,
    CONSTRAINT ck_notificaciones_notificaciones_tipo_check CHECK ((tipo = ANY (ARRAY['info'::text, 'alerta'::text, 'error'::text, 'mantenimiento'::text, 'reserva'::text, 'sistema'::text])))
);


--
-- Name: permisos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.permisos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: proveedores; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.proveedores (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    contacto text,
    direccion text,
    sitio_web text,
    rnc text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.refresh_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    usuario_id uuid NOT NULL,
    token_hash character varying(256) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    revoked_at timestamp with time zone,
    ip_address character varying(100),
    user_agent text
);


--
-- Name: reportes; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.reportes (
    id uuid NOT NULL,
    usuario_id uuid NOT NULL,
    tipo_reporte character varying NOT NULL,
    formato character varying NOT NULL,
    parametros jsonb,
    estado character varying NOT NULL,
    archivo_path character varying,
    archivo_size_bytes integer,
    error_msg text,
    fecha_solicitud timestamp with time zone DEFAULT now() NOT NULL,
    fecha_completado timestamp with time zone
);


--
-- Name: reservas_equipo; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.reservas_equipo (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    equipo_id uuid NOT NULL,
    usuario_solicitante_id uuid NOT NULL,
    fecha_hora_inicio timestamp with time zone NOT NULL,
    fecha_hora_fin timestamp with time zone NOT NULL,
    proposito text,
    estado text DEFAULT 'Confirmada'::text NOT NULL,
    notas text,
    notas_administrador text,
    notas_devolucion text,
    created_at timestamp with time zone DEFAULT now(),
    aprobado_por_id uuid,
    fecha_aprobacion timestamp with time zone,
    check_in_time timestamp with time zone,
    check_out_time timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    componentes_origen jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT ck_reservas_equipo_check_fechas_reserva CHECK ((fecha_hora_fin > fecha_hora_inicio)),
    CONSTRAINT ck_reservas_equipo_reservas_equipo_estado_check CHECK ((estado = ANY (ARRAY['Confirmada'::text, 'Pendiente Aprobacion'::text, 'Cancelada'::text, 'Cancelada por Usuario'::text, 'Cancelada por Gestor'::text, 'Rechazada'::text, 'Finalizada'::text, 'En Curso'::text])))
);


--
-- Name: roles; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: roles_permisos; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.roles_permisos (
    rol_id uuid NOT NULL,
    permiso_id uuid NOT NULL,
    otorgado_por uuid,
    fecha_otorgamiento timestamp with time zone DEFAULT now()
);


--
-- Name: software_catalogo; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.software_catalogo (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    version text,
    descripcion text,
    categoria text,
    tipo_licencia text NOT NULL,
    metrica_licenciamiento text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL,
    marca_id uuid,
    CONSTRAINT ck_software_catalogo_software_catalogo_metrica_licencia_825f CHECK ((metrica_licenciamiento = ANY (ARRAY['Por Dispositivo'::text, 'Por Usuario Nominal'::text, 'Por Usuario Concurrente'::text, 'Por Core'::text, 'Por Servidor'::text, 'Gratuita'::text, 'Otra'::text]))),
    CONSTRAINT ck_software_catalogo_software_catalogo_tipo_licencia_check CHECK ((tipo_licencia = ANY (ARRAY['Perpetua'::text, 'Suscripción Anual'::text, 'Suscripción Mensual'::text, 'OEM'::text, 'Freeware'::text, 'Open Source'::text, 'Otra'::text])))
);


--
-- Name: tecnicos_mantenimiento; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.tecnicos_mantenimiento (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre_completo character varying(255) NOT NULL,
    es_externo boolean DEFAULT false NOT NULL,
    proveedor_id uuid,
    telefono_contacto character varying(50),
    email_contacto character varying(100),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tipos_documento; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.tipos_documento (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    requiere_verificacion boolean DEFAULT false,
    formato_permitido text[],
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: tipos_item_inventario; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.tipos_item_inventario (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    categoria text NOT NULL,
    unidad_medida text DEFAULT 'Unidad'::text NOT NULL,
    modelo text,
    sku text,
    codigo_barras text,
    modelos_equipo_compatibles text[],
    proveedor_preferido_id uuid,
    stock_minimo integer DEFAULT 0,
    perecedero boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL,
    marca_id uuid,
    color character varying(30),
    tecnologia character varying(30),
    rendimiento_paginas integer,
    es_original boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_tipos_item_inventario_rendimiento_positivo CHECK (((rendimiento_paginas IS NULL) OR (rendimiento_paginas > 0))),
    CONSTRAINT ck_tipos_item_inventario_tipos_item_inventario_categoria_check CHECK ((categoria = ANY (ARRAY['Consumible'::text, 'Parte Repuesto'::text, 'Accesorio'::text, 'Otro'::text]))),
    CONSTRAINT ck_tipos_item_inventario_tipos_item_inventario_stock_mi_1796 CHECK ((stock_minimo >= 0))
);


--
-- Name: usuarios; Type: TABLE; Schema: control_equipos; Owner: -
--

CREATE TABLE control_equipos.usuarios (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nombre_usuario text NOT NULL,
    contrasena text NOT NULL,
    rol_id uuid NOT NULL,
    email text,
    token_temporal uuid,
    token_expiracion timestamp with time zone,
    intentos_fallidos integer DEFAULT 0,
    bloqueado boolean DEFAULT false,
    ultimo_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    requiere_cambio_contrasena boolean DEFAULT true,
    is_active boolean DEFAULT true NOT NULL,
    avatar_url text,
    departamento_id uuid,
    empleado_id uuid,
    session_version integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_usuarios_check_email_format CHECK (((email IS NULL) OR (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'::text))),
    CONSTRAINT usuarios_session_version_check CHECK ((session_version >= 0))
);


--
-- Name: audit_log_y2026m10; Type: TABLE ATTACH; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.audit_log ATTACH PARTITION control_equipos.audit_log_y2026m10 FOR VALUES FROM ('2026-10-01 00:00:00-04') TO ('2026-11-01 00:00:00-04');


--
-- Name: audit_log_y2026m11; Type: TABLE ATTACH; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.audit_log ATTACH PARTITION control_equipos.audit_log_y2026m11 FOR VALUES FROM ('2026-11-01 00:00:00-04') TO ('2026-12-01 00:00:00-04');


--
-- Name: configuracion_empresa id; Type: DEFAULT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.configuracion_empresa ALTER COLUMN id SET DEFAULT nextval('control_equipos.configuracion_empresa_id_seq'::regclass);


--
-- Name: audit_log pk_audit_log; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.audit_log
    ADD CONSTRAINT pk_audit_log PRIMARY KEY (audit_timestamp, id);


--
-- Name: audit_log_y2026m10 audit_log_y2026m10_pkey; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.audit_log_y2026m10
    ADD CONSTRAINT audit_log_y2026m10_pkey PRIMARY KEY (audit_timestamp, id);


--
-- Name: audit_log_y2026m11 audit_log_y2026m11_pkey; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.audit_log_y2026m11
    ADD CONSTRAINT audit_log_y2026m11_pkey PRIMARY KEY (audit_timestamp, id);


--
-- Name: asignaciones_licencia pk_asignaciones_licencia; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.asignaciones_licencia
    ADD CONSTRAINT pk_asignaciones_licencia PRIMARY KEY (id);


--
-- Name: backup_logs pk_backup_logs; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.backup_logs
    ADD CONSTRAINT pk_backup_logs PRIMARY KEY (id);


--
-- Name: configuracion_empresa pk_configuracion_empresa; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.configuracion_empresa
    ADD CONSTRAINT pk_configuracion_empresa PRIMARY KEY (id);


--
-- Name: departamentos pk_departamentos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.departamentos
    ADD CONSTRAINT pk_departamentos PRIMARY KEY (id);


--
-- Name: documentacion pk_documentacion; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT pk_documentacion PRIMARY KEY (id);


--
-- Name: empleados pk_empleados; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.empleados
    ADD CONSTRAINT pk_empleados PRIMARY KEY (id);


--
-- Name: equipo_componentes pk_equipo_componentes; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipo_componentes
    ADD CONSTRAINT pk_equipo_componentes PRIMARY KEY (id);


--
-- Name: equipos pk_equipos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT pk_equipos PRIMARY KEY (id);


--
-- Name: estados_equipo pk_estados_equipo; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.estados_equipo
    ADD CONSTRAINT pk_estados_equipo PRIMARY KEY (id);


--
-- Name: inventario_movimientos pk_inventario_movimientos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT pk_inventario_movimientos PRIMARY KEY (id);


--
-- Name: inventario_stock pk_inventario_stock; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_stock
    ADD CONSTRAINT pk_inventario_stock PRIMARY KEY (id);


--
-- Name: licencias_software pk_licencias_software; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.licencias_software
    ADD CONSTRAINT pk_licencias_software PRIMARY KEY (id);


--
-- Name: login_logs pk_login_logs; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.login_logs
    ADD CONSTRAINT pk_login_logs PRIMARY KEY (id);


--
-- Name: mantenimiento pk_mantenimiento; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.mantenimiento
    ADD CONSTRAINT pk_mantenimiento PRIMARY KEY (id);


--
-- Name: marcas pk_marcas; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.marcas
    ADD CONSTRAINT pk_marcas PRIMARY KEY (id);


--
-- Name: movimientos pk_movimientos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT pk_movimientos PRIMARY KEY (id);


--
-- Name: notificaciones pk_notificaciones; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.notificaciones
    ADD CONSTRAINT pk_notificaciones PRIMARY KEY (id);


--
-- Name: permisos pk_permisos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.permisos
    ADD CONSTRAINT pk_permisos PRIMARY KEY (id);


--
-- Name: proveedores pk_proveedores; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.proveedores
    ADD CONSTRAINT pk_proveedores PRIMARY KEY (id);


--
-- Name: refresh_tokens pk_refresh_tokens; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.refresh_tokens
    ADD CONSTRAINT pk_refresh_tokens PRIMARY KEY (id);


--
-- Name: reportes pk_reportes; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reportes
    ADD CONSTRAINT pk_reportes PRIMARY KEY (id);


--
-- Name: reservas_equipo pk_reservas_equipo; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reservas_equipo
    ADD CONSTRAINT pk_reservas_equipo PRIMARY KEY (id);


--
-- Name: roles pk_roles; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles
    ADD CONSTRAINT pk_roles PRIMARY KEY (id);


--
-- Name: roles_permisos pk_roles_permisos; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles_permisos
    ADD CONSTRAINT pk_roles_permisos PRIMARY KEY (rol_id, permiso_id);


--
-- Name: software_catalogo pk_software_catalogo; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.software_catalogo
    ADD CONSTRAINT pk_software_catalogo PRIMARY KEY (id);


--
-- Name: tecnicos_mantenimiento pk_tecnicos_mantenimiento; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tecnicos_mantenimiento
    ADD CONSTRAINT pk_tecnicos_mantenimiento PRIMARY KEY (id);


--
-- Name: tipos_documento pk_tipos_documento; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_documento
    ADD CONSTRAINT pk_tipos_documento PRIMARY KEY (id);


--
-- Name: tipos_item_inventario pk_tipos_item_inventario; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT pk_tipos_item_inventario PRIMARY KEY (id);


--
-- Name: tipos_mantenimiento pk_tipos_mantenimiento; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_mantenimiento
    ADD CONSTRAINT pk_tipos_mantenimiento PRIMARY KEY (id);


--
-- Name: ubicaciones pk_ubicaciones; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.ubicaciones
    ADD CONSTRAINT pk_ubicaciones PRIMARY KEY (id);


--
-- Name: usuarios pk_usuarios; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT pk_usuarios PRIMARY KEY (id);


--
-- Name: reservas_equipo reservas_equipo_solapamiento_excl; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reservas_equipo
    ADD CONSTRAINT reservas_equipo_solapamiento_excl EXCLUDE USING gist (equipo_id WITH =, tstzrange(fecha_hora_inicio, fecha_hora_fin, '()'::text) WITH &&) WHERE ((estado = ANY (ARRAY['Confirmada'::text, 'Pendiente Aprobacion'::text, 'En Curso'::text])));


--
-- Name: equipo_componentes uq_componente; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipo_componentes
    ADD CONSTRAINT uq_componente UNIQUE (equipo_padre_id, equipo_componente_id, tipo_relacion);


--
-- Name: equipos uq_equipos_codigo_interno; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT uq_equipos_codigo_interno UNIQUE (codigo_interno);


--
-- Name: equipos uq_equipos_numero_serie; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT uq_equipos_numero_serie UNIQUE (numero_serie);


--
-- Name: estados_equipo uq_estados_equipo_codigo; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.estados_equipo
    ADD CONSTRAINT uq_estados_equipo_codigo UNIQUE (codigo);


--
-- Name: estados_equipo uq_estados_equipo_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.estados_equipo
    ADD CONSTRAINT uq_estados_equipo_nombre UNIQUE (nombre);


--
-- Name: inventario_stock uq_item_ubicacion_lote; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_stock
    ADD CONSTRAINT uq_item_ubicacion_lote UNIQUE (tipo_item_id, ubicacion_id, lote);


--
-- Name: permisos uq_permisos_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.permisos
    ADD CONSTRAINT uq_permisos_nombre UNIQUE (nombre);


--
-- Name: proveedores uq_proveedores_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.proveedores
    ADD CONSTRAINT uq_proveedores_nombre UNIQUE (nombre);


--
-- Name: refresh_tokens uq_refresh_tokens_token_hash; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.refresh_tokens
    ADD CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash);


--
-- Name: roles uq_roles_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles
    ADD CONSTRAINT uq_roles_nombre UNIQUE (nombre);


--
-- Name: software_catalogo uq_software_nombre_version; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.software_catalogo
    ADD CONSTRAINT uq_software_nombre_version UNIQUE (nombre, version);


--
-- Name: tipos_documento uq_tipos_documento_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_documento
    ADD CONSTRAINT uq_tipos_documento_nombre UNIQUE (nombre);


--
-- Name: tipos_item_inventario uq_tipos_item_inventario_codigo_barras; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT uq_tipos_item_inventario_codigo_barras UNIQUE (codigo_barras);


--
-- Name: tipos_item_inventario uq_tipos_item_inventario_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT uq_tipos_item_inventario_nombre UNIQUE (nombre);


--
-- Name: tipos_item_inventario uq_tipos_item_inventario_sku; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT uq_tipos_item_inventario_sku UNIQUE (sku);


--
-- Name: tipos_mantenimiento uq_tipos_mantenimiento_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_mantenimiento
    ADD CONSTRAINT uq_tipos_mantenimiento_nombre UNIQUE (nombre);


--
-- Name: ubicaciones uq_ubicaciones_nombre; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.ubicaciones
    ADD CONSTRAINT uq_ubicaciones_nombre UNIQUE (nombre);


--
-- Name: usuarios uq_usuarios_email; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT uq_usuarios_email UNIQUE (email);


--
-- Name: usuarios uq_usuarios_nombre_usuario; Type: CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT uq_usuarios_nombre_usuario UNIQUE (nombre_usuario);


--
-- Name: idx_documentacion_licencia_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_documentacion_licencia_id ON control_equipos.documentacion USING btree (licencia_id) WHERE (licencia_id IS NOT NULL);


--
-- Name: idx_documentacion_mantenimiento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_documentacion_mantenimiento_id ON control_equipos.documentacion USING btree (mantenimiento_id) WHERE (mantenimiento_id IS NOT NULL);


--
-- Name: idx_documentacion_texto_busqueda; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_documentacion_texto_busqueda ON control_equipos.documentacion USING gin (texto_busqueda);


--
-- Name: idx_documentacion_titulo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_documentacion_titulo ON control_equipos.documentacion USING btree (titulo);


--
-- Name: idx_equipos_texto_busqueda; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_equipos_texto_busqueda ON control_equipos.equipos USING gin (texto_busqueda);


--
-- Name: idx_inventario_movimientos_ref_transferencia; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_inventario_movimientos_ref_transferencia ON control_equipos.inventario_movimientos USING btree (referencia_transferencia) WHERE (referencia_transferencia IS NOT NULL);


--
-- Name: idx_licencias_software_clave_producto; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_licencias_software_clave_producto ON control_equipos.licencias_software USING btree (clave_producto) WHERE (clave_producto IS NOT NULL);


--
-- Name: idx_login_logs_exito_intento; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_login_logs_exito_intento ON control_equipos.login_logs USING btree (exito, intento);


--
-- Name: idx_mantenimiento_fecha_finalizacion; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_fecha_finalizacion ON control_equipos.mantenimiento USING btree (fecha_finalizacion) WHERE (fecha_finalizacion IS NOT NULL);


--
-- Name: idx_mantenimiento_fecha_inicio; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_fecha_inicio ON control_equipos.mantenimiento USING btree (fecha_inicio) WHERE (fecha_inicio IS NOT NULL);


--
-- Name: idx_mantenimiento_fecha_programada; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_fecha_programada ON control_equipos.mantenimiento USING btree (fecha_programada) WHERE (fecha_programada IS NOT NULL);


--
-- Name: idx_mantenimiento_fecha_proximo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_fecha_proximo ON control_equipos.mantenimiento USING btree (fecha_proximo_mantenimiento) WHERE (fecha_proximo_mantenimiento IS NOT NULL);


--
-- Name: idx_mantenimiento_prioridad; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_prioridad ON control_equipos.mantenimiento USING btree (prioridad);


--
-- Name: idx_mantenimiento_texto_busqueda; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mantenimiento_texto_busqueda ON control_equipos.mantenimiento USING gin (texto_busqueda);


--
-- Name: idx_mv_equipos_estado_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX idx_mv_equipos_estado_id ON control_equipos.mv_equipos_estado USING btree (estado_id);


--
-- Name: idx_mv_mantenimientos_proximos_equipo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mv_mantenimientos_proximos_equipo ON control_equipos.mv_mantenimientos_proximos USING btree (equipo_id);


--
-- Name: idx_mv_mantenimientos_proximos_fecha; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_mv_mantenimientos_proximos_fecha ON control_equipos.mv_mantenimientos_proximos USING btree (fecha_proximo_mantenimiento);


--
-- Name: idx_mv_mantenimientos_proximos_mantenimiento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX idx_mv_mantenimientos_proximos_mantenimiento_id ON control_equipos.mv_mantenimientos_proximos USING btree (mantenimiento_id);


--
-- Name: idx_notificaciones_usuario_id_leido_urgencia; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_notificaciones_usuario_id_leido_urgencia ON control_equipos.notificaciones USING btree (usuario_id, leido, urgencia, created_at);


--
-- Name: idx_reservas_equipo_rango_gist; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_reservas_equipo_rango_gist ON control_equipos.reservas_equipo USING gist (equipo_id, tstzrange(fecha_hora_inicio, fecha_hora_fin, '()'::text));


--
-- Name: idx_reservas_fechas; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX idx_reservas_fechas ON control_equipos.reservas_equipo USING btree (fecha_hora_inicio, fecha_hora_fin);


--
-- Name: ix_control_equipos_asignaciones_licencia_equipo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_asignaciones_licencia_equipo_id ON control_equipos.asignaciones_licencia USING btree (equipo_id) WHERE (equipo_id IS NOT NULL);


--
-- Name: ix_control_equipos_asignaciones_licencia_licencia_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_asignaciones_licencia_licencia_id ON control_equipos.asignaciones_licencia USING btree (licencia_id);


--
-- Name: ix_control_equipos_asignaciones_licencia_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_asignaciones_licencia_usuario_id ON control_equipos.asignaciones_licencia USING btree (usuario_id) WHERE (usuario_id IS NOT NULL);


--
-- Name: ix_control_equipos_departamentos_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_departamentos_nombre ON control_equipos.departamentos USING btree (nombre);


--
-- Name: ix_control_equipos_documentacion_equipo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_documentacion_equipo_id ON control_equipos.documentacion USING btree (equipo_id);


--
-- Name: ix_control_equipos_documentacion_estado; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_documentacion_estado ON control_equipos.documentacion USING btree (estado);


--
-- Name: ix_control_equipos_documentacion_subido_por; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_documentacion_subido_por ON control_equipos.documentacion USING btree (subido_por);


--
-- Name: ix_control_equipos_documentacion_tipo_documento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_documentacion_tipo_documento_id ON control_equipos.documentacion USING btree (tipo_documento_id);


--
-- Name: ix_control_equipos_empleados_departamento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_empleados_departamento_id ON control_equipos.empleados USING btree (departamento_id);


--
-- Name: ix_control_equipos_empleados_email_corporativo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_empleados_email_corporativo ON control_equipos.empleados USING btree (email_corporativo);


--
-- Name: ix_control_equipos_empleados_nombre_completo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_empleados_nombre_completo ON control_equipos.empleados USING btree (nombre_completo);


--
-- Name: ix_control_equipos_equipo_componentes_equipo_componente_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipo_componentes_equipo_componente_id ON control_equipos.equipo_componentes USING btree (equipo_componente_id);


--
-- Name: ix_control_equipos_equipo_componentes_equipo_padre_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipo_componentes_equipo_padre_id ON control_equipos.equipo_componentes USING btree (equipo_padre_id);


--
-- Name: ix_control_equipos_equipos_centro_costo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_centro_costo ON control_equipos.equipos USING btree (centro_costo);


--
-- Name: ix_control_equipos_equipos_codigo_interno; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_equipos_codigo_interno ON control_equipos.equipos USING btree (codigo_interno) WHERE (codigo_interno IS NOT NULL);


--
-- Name: ix_control_equipos_equipos_empleado_asignado_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_empleado_asignado_id ON control_equipos.equipos USING btree (empleado_asignado_id);


--
-- Name: ix_control_equipos_equipos_estado_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_estado_id ON control_equipos.equipos USING btree (estado_id);


--
-- Name: ix_control_equipos_equipos_marca_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_marca_id ON control_equipos.equipos USING btree (marca_id);


--
-- Name: ix_control_equipos_equipos_modelo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_modelo ON control_equipos.equipos USING btree (modelo);


--
-- Name: ix_control_equipos_equipos_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_nombre ON control_equipos.equipos USING btree (nombre);


--
-- Name: ix_control_equipos_equipos_numero_serie; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_equipos_numero_serie ON control_equipos.equipos USING btree (numero_serie);


--
-- Name: ix_control_equipos_equipos_proveedor_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_equipos_proveedor_id ON control_equipos.equipos USING btree (proveedor_id);


--
-- Name: ix_control_equipos_inventario_movimientos_equipo_asociado_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_equipo_asociado_id ON control_equipos.inventario_movimientos USING btree (equipo_asociado_id);


--
-- Name: ix_control_equipos_inventario_movimientos_fecha_hora; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_fecha_hora ON control_equipos.inventario_movimientos USING btree (fecha_hora);


--
-- Name: ix_control_equipos_inventario_movimientos_mantenimiento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_mantenimiento_id ON control_equipos.inventario_movimientos USING btree (mantenimiento_id);


--
-- Name: ix_control_equipos_inventario_movimientos_tipo_item_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_tipo_item_id ON control_equipos.inventario_movimientos USING btree (tipo_item_id);


--
-- Name: ix_control_equipos_inventario_movimientos_tipo_movimiento; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_tipo_movimiento ON control_equipos.inventario_movimientos USING btree (tipo_movimiento);


--
-- Name: ix_control_equipos_inventario_movimientos_ubicacion_destino_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_ubicacion_destino_id ON control_equipos.inventario_movimientos USING btree (ubicacion_destino_id);


--
-- Name: ix_control_equipos_inventario_movimientos_ubicacion_origen_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_ubicacion_origen_id ON control_equipos.inventario_movimientos USING btree (ubicacion_origen_id);


--
-- Name: ix_control_equipos_inventario_movimientos_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_movimientos_usuario_id ON control_equipos.inventario_movimientos USING btree (usuario_id);


--
-- Name: ix_control_equipos_inventario_stock_fecha_caducidad; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_stock_fecha_caducidad ON control_equipos.inventario_stock USING btree (fecha_caducidad) WHERE (fecha_caducidad IS NOT NULL);


--
-- Name: ix_control_equipos_inventario_stock_tipo_item_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_stock_tipo_item_id ON control_equipos.inventario_stock USING btree (tipo_item_id);


--
-- Name: ix_control_equipos_inventario_stock_ubicacion_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_inventario_stock_ubicacion_id ON control_equipos.inventario_stock USING btree (ubicacion_id);


--
-- Name: ix_control_equipos_licencias_software_fecha_expiracion; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_licencias_software_fecha_expiracion ON control_equipos.licencias_software USING btree (fecha_expiracion);


--
-- Name: ix_control_equipos_licencias_software_proveedor_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_licencias_software_proveedor_id ON control_equipos.licencias_software USING btree (proveedor_id);


--
-- Name: ix_control_equipos_licencias_software_software_catalogo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_licencias_software_software_catalogo_id ON control_equipos.licencias_software USING btree (software_catalogo_id);


--
-- Name: ix_control_equipos_login_logs_intento; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_login_logs_intento ON control_equipos.login_logs USING btree (intento);


--
-- Name: ix_control_equipos_login_logs_ip_origen; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_login_logs_ip_origen ON control_equipos.login_logs USING btree (ip_origen);


--
-- Name: ix_control_equipos_login_logs_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_login_logs_usuario_id ON control_equipos.login_logs USING btree (usuario_id);


--
-- Name: ix_control_equipos_mantenimiento_equipo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_mantenimiento_equipo_id ON control_equipos.mantenimiento USING btree (equipo_id);


--
-- Name: ix_control_equipos_mantenimiento_estado; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_mantenimiento_estado ON control_equipos.mantenimiento USING btree (estado);


--
-- Name: ix_control_equipos_mantenimiento_tecnico_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_mantenimiento_tecnico_id ON control_equipos.mantenimiento USING btree (tecnico_id);


--
-- Name: ix_control_equipos_mantenimiento_tipo_mantenimiento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_mantenimiento_tipo_mantenimiento_id ON control_equipos.mantenimiento USING btree (tipo_mantenimiento_id);


--
-- Name: ix_control_equipos_marcas_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_marcas_nombre ON control_equipos.marcas USING btree (nombre);


--
-- Name: ix_control_equipos_movimientos_autorizado_por; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_autorizado_por ON control_equipos.movimientos USING btree (autorizado_por);


--
-- Name: ix_control_equipos_movimientos_empleado_destino_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_empleado_destino_id ON control_equipos.movimientos USING btree (empleado_destino_id);


--
-- Name: ix_control_equipos_movimientos_equipo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_equipo_id ON control_equipos.movimientos USING btree (equipo_id);


--
-- Name: ix_control_equipos_movimientos_estado; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_estado ON control_equipos.movimientos USING btree (estado);


--
-- Name: ix_control_equipos_movimientos_fecha_hora; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_fecha_hora ON control_equipos.movimientos USING btree (fecha_hora);


--
-- Name: ix_control_equipos_movimientos_tipo_movimiento; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_tipo_movimiento ON control_equipos.movimientos USING btree (tipo_movimiento);


--
-- Name: ix_control_equipos_movimientos_ubicacion_destino_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_ubicacion_destino_id ON control_equipos.movimientos USING btree (ubicacion_destino_id);


--
-- Name: ix_control_equipos_movimientos_ubicacion_origen_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_ubicacion_origen_id ON control_equipos.movimientos USING btree (ubicacion_origen_id);


--
-- Name: ix_control_equipos_movimientos_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_movimientos_usuario_id ON control_equipos.movimientos USING btree (usuario_id);


--
-- Name: ix_control_equipos_notificaciones_created_at; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_notificaciones_created_at ON control_equipos.notificaciones USING btree (created_at);


--
-- Name: ix_control_equipos_permisos_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_permisos_nombre ON control_equipos.permisos USING btree (nombre);


--
-- Name: ix_control_equipos_proveedores_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_proveedores_nombre ON control_equipos.proveedores USING btree (nombre);


--
-- Name: ix_control_equipos_refresh_tokens_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_refresh_tokens_usuario_id ON control_equipos.refresh_tokens USING btree (usuario_id);


--
-- Name: ix_control_equipos_reportes_estado; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reportes_estado ON control_equipos.reportes USING btree (estado);


--
-- Name: ix_control_equipos_reportes_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reportes_id ON control_equipos.reportes USING btree (id);


--
-- Name: ix_control_equipos_reportes_tipo_reporte; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reportes_tipo_reporte ON control_equipos.reportes USING btree (tipo_reporte);


--
-- Name: ix_control_equipos_reportes_usuario_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reportes_usuario_id ON control_equipos.reportes USING btree (usuario_id);


--
-- Name: ix_control_equipos_reservas_equipo_equipo_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reservas_equipo_equipo_id ON control_equipos.reservas_equipo USING btree (equipo_id);


--
-- Name: ix_control_equipos_reservas_equipo_estado; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reservas_equipo_estado ON control_equipos.reservas_equipo USING btree (estado);


--
-- Name: ix_control_equipos_reservas_equipo_usuario_solicitante_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_reservas_equipo_usuario_solicitante_id ON control_equipos.reservas_equipo USING btree (usuario_solicitante_id);


--
-- Name: ix_control_equipos_roles_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_roles_nombre ON control_equipos.roles USING btree (nombre);


--
-- Name: ix_control_equipos_roles_permisos_permiso_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_roles_permisos_permiso_id ON control_equipos.roles_permisos USING btree (permiso_id);


--
-- Name: ix_control_equipos_software_catalogo_marca_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_software_catalogo_marca_id ON control_equipos.software_catalogo USING btree (marca_id);


--
-- Name: ix_control_equipos_software_catalogo_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_software_catalogo_nombre ON control_equipos.software_catalogo USING btree (nombre);


--
-- Name: ix_control_equipos_tecnicos_mantenimiento_proveedor_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_tecnicos_mantenimiento_proveedor_id ON control_equipos.tecnicos_mantenimiento USING btree (proveedor_id);


--
-- Name: ix_control_equipos_tipos_documento_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_tipos_documento_nombre ON control_equipos.tipos_documento USING btree (nombre);


--
-- Name: ix_control_equipos_tipos_item_inventario_categoria; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_tipos_item_inventario_categoria ON control_equipos.tipos_item_inventario USING btree (categoria);


--
-- Name: ix_control_equipos_tipos_item_inventario_codigo_barras; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_tipos_item_inventario_codigo_barras ON control_equipos.tipos_item_inventario USING btree (codigo_barras) WHERE (codigo_barras IS NOT NULL);


--
-- Name: ix_control_equipos_tipos_item_inventario_marca_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_tipos_item_inventario_marca_id ON control_equipos.tipos_item_inventario USING btree (marca_id);


--
-- Name: ix_control_equipos_tipos_item_inventario_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_tipos_item_inventario_nombre ON control_equipos.tipos_item_inventario USING btree (nombre);


--
-- Name: ix_control_equipos_tipos_item_inventario_sku; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_tipos_item_inventario_sku ON control_equipos.tipos_item_inventario USING btree (sku) WHERE (sku IS NOT NULL);


--
-- Name: ix_control_equipos_tipos_mantenimiento_nombre; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_tipos_mantenimiento_nombre ON control_equipos.tipos_mantenimiento USING btree (nombre);


--
-- Name: ix_control_equipos_ubicaciones_departamento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_ubicaciones_departamento_id ON control_equipos.ubicaciones USING btree (departamento_id);


--
-- Name: ix_control_equipos_usuarios_departamento_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_usuarios_departamento_id ON control_equipos.usuarios USING btree (departamento_id);


--
-- Name: ix_control_equipos_usuarios_email; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_usuarios_email ON control_equipos.usuarios USING btree (email);


--
-- Name: ix_control_equipos_usuarios_empleado_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_usuarios_empleado_id ON control_equipos.usuarios USING btree (empleado_id);


--
-- Name: ix_control_equipos_usuarios_nombre_usuario; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX ix_control_equipos_usuarios_nombre_usuario ON control_equipos.usuarios USING btree (nombre_usuario);


--
-- Name: ix_control_equipos_usuarios_rol_id; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE INDEX ix_control_equipos_usuarios_rol_id ON control_equipos.usuarios USING btree (rol_id);


--
-- Name: uq_asignacion_licencia_equipo; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX uq_asignacion_licencia_equipo ON control_equipos.asignaciones_licencia USING btree (licencia_id, equipo_id) WHERE (equipo_id IS NOT NULL);


--
-- Name: uq_asignacion_licencia_usuario; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX uq_asignacion_licencia_usuario ON control_equipos.asignaciones_licencia USING btree (licencia_id, usuario_id) WHERE (usuario_id IS NOT NULL);


--
-- Name: uq_equipos_serie_normalizada; Type: INDEX; Schema: control_equipos; Owner: -
--

CREATE UNIQUE INDEX uq_equipos_serie_normalizada ON control_equipos.equipos USING btree (upper(btrim(numero_serie)));


--
-- Name: audit_log_y2026m10_pkey; Type: INDEX ATTACH; Schema: control_equipos; Owner: -
--

ALTER INDEX control_equipos.pk_audit_log ATTACH PARTITION control_equipos.audit_log_y2026m10_pkey;


--
-- Name: audit_log_y2026m11_pkey; Type: INDEX ATTACH; Schema: control_equipos; Owner: -
--

ALTER INDEX control_equipos.pk_audit_log ATTACH PARTITION control_equipos.audit_log_y2026m11_pkey;


--
-- Name: asignaciones_licencia asignaciones_licencia_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER asignaciones_licencia_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.asignaciones_licencia FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: documentacion documentacion_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER documentacion_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.documentacion FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: equipo_componentes equipo_componentes_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER equipo_componentes_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.equipo_componentes FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: equipos equipos_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER equipos_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.equipos FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: estados_equipo estados_equipo_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER estados_equipo_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.estados_equipo FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: inventario_movimientos inventario_movimientos_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER inventario_movimientos_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.inventario_movimientos FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: inventario_stock inventario_stock_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER inventario_stock_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.inventario_stock FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: licencias_software licencias_software_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER licencias_software_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.licencias_software FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: login_logs login_logs_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER login_logs_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.login_logs FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: mantenimiento mantenimiento_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER mantenimiento_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.mantenimiento FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: movimientos movimientos_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER movimientos_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.movimientos FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: notificaciones notificaciones_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER notificaciones_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.notificaciones FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: notificaciones notificaciones_tiempo_real; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER notificaciones_tiempo_real AFTER INSERT OR DELETE OR UPDATE ON control_equipos.notificaciones FOR EACH ROW EXECUTE FUNCTION control_equipos.notificar_cambio_notificacion();


--
-- Name: permisos permisos_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER permisos_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.permisos FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: inventario_movimientos proteger_ledger_inventario; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER proteger_ledger_inventario BEFORE DELETE OR UPDATE ON control_equipos.inventario_movimientos FOR EACH ROW EXECUTE FUNCTION control_equipos.proteger_ledger_inventario();


--
-- Name: proveedores proveedores_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER proveedores_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.proveedores FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: refresh_tokens refresh_tokens_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER refresh_tokens_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.refresh_tokens FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: reservas_equipo reservas_equipo_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER reservas_equipo_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.reservas_equipo FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: roles roles_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER roles_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.roles FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: roles_permisos roles_permisos_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER roles_permisos_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.roles_permisos FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: software_catalogo software_catalogo_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER software_catalogo_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.software_catalogo FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: inventario_stock stock_claves_inmutables; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER stock_claves_inmutables BEFORE UPDATE ON control_equipos.inventario_stock FOR EACH ROW EXECUTE FUNCTION control_equipos.proteger_claves_stock();


--
-- Name: tipos_documento tipos_documento_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER tipos_documento_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.tipos_documento FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: tipos_item_inventario tipos_item_inventario_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER tipos_item_inventario_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.tipos_item_inventario FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: tipos_mantenimiento tipos_mantenimiento_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER tipos_mantenimiento_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.tipos_mantenimiento FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: inventario_movimientos transferencia_completa; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE CONSTRAINT TRIGGER transferencia_completa AFTER INSERT ON control_equipos.inventario_movimientos DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION control_equipos.validar_transferencia_inventario();


--
-- Name: mantenimiento trg_actualizar_fecha_proximo_mantenimiento; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_actualizar_fecha_proximo_mantenimiento BEFORE INSERT OR UPDATE ON control_equipos.mantenimiento FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_fecha_proximo_mantenimiento();


--
-- Name: inventario_movimientos trg_actualizar_inventario_stock; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_actualizar_inventario_stock AFTER INSERT ON control_equipos.inventario_movimientos FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_inventario_stock_fn();


--
-- Name: asignaciones_licencia trg_actualizar_licencia_disponible; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_actualizar_licencia_disponible AFTER INSERT OR DELETE ON control_equipos.asignaciones_licencia FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_licencia_disponible_fn();


--
-- Name: documentacion trg_documentacion_texto_busqueda; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_documentacion_texto_busqueda BEFORE INSERT OR UPDATE ON control_equipos.documentacion FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_busqueda_documento();


--
-- Name: equipos trg_equipos_texto_busqueda; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_equipos_texto_busqueda BEFORE INSERT OR UPDATE ON control_equipos.equipos FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_busqueda_equipo();


--
-- Name: mantenimiento trg_mantenimiento_texto_busqueda; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_mantenimiento_texto_busqueda BEFORE INSERT OR UPDATE ON control_equipos.mantenimiento FOR EACH ROW EXECUTE FUNCTION control_equipos.actualizar_busqueda_mantenimiento();


--
-- Name: equipos trg_update_equipo_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_equipo_updated_at BEFORE UPDATE ON control_equipos.equipos FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: licencias_software trg_update_licencias_software_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_licencias_software_updated_at BEFORE UPDATE ON control_equipos.licencias_software FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: mantenimiento trg_update_mantenimiento_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_mantenimiento_updated_at BEFORE UPDATE ON control_equipos.mantenimiento FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: proveedores trg_update_proveedores_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_proveedores_updated_at BEFORE UPDATE ON control_equipos.proveedores FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: reservas_equipo trg_update_reserva_equipo_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_reserva_equipo_updated_at BEFORE UPDATE ON control_equipos.reservas_equipo FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: software_catalogo trg_update_software_catalogo_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_software_catalogo_updated_at BEFORE UPDATE ON control_equipos.software_catalogo FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: tipos_item_inventario trg_update_tipos_item_inv_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_tipos_item_inv_updated_at BEFORE UPDATE ON control_equipos.tipos_item_inventario FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: usuarios trg_update_usuario_updated_at; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER trg_update_usuario_updated_at BEFORE UPDATE ON control_equipos.usuarios FOR EACH ROW WHEN ((old.* IS DISTINCT FROM new.*)) EXECUTE FUNCTION control_equipos.update_updated_at();


--
-- Name: usuarios usuarios_audit_trigger; Type: TRIGGER; Schema: control_equipos; Owner: -
--

CREATE TRIGGER usuarios_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON control_equipos.usuarios FOR EACH ROW EXECUTE FUNCTION control_equipos.audit_trigger_fn();


--
-- Name: asignaciones_licencia fk_asignaciones_licencia_equipo_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.asignaciones_licencia
    ADD CONSTRAINT fk_asignaciones_licencia_equipo_id_equipos FOREIGN KEY (equipo_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: asignaciones_licencia fk_asignaciones_licencia_licencia_id_licencias_software; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.asignaciones_licencia
    ADD CONSTRAINT fk_asignaciones_licencia_licencia_id_licencias_software FOREIGN KEY (licencia_id) REFERENCES control_equipos.licencias_software(id) ON DELETE CASCADE;


--
-- Name: asignaciones_licencia fk_asignaciones_licencia_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.asignaciones_licencia
    ADD CONSTRAINT fk_asignaciones_licencia_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE CASCADE;


--
-- Name: documentacion fk_documentacion_equipo_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_equipo_id_equipos FOREIGN KEY (equipo_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: documentacion fk_documentacion_licencia_id_licencias_software; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_licencia_id_licencias_software FOREIGN KEY (licencia_id) REFERENCES control_equipos.licencias_software(id) ON DELETE SET NULL;


--
-- Name: documentacion fk_documentacion_mantenimiento_id_mantenimiento; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_mantenimiento_id_mantenimiento FOREIGN KEY (mantenimiento_id) REFERENCES control_equipos.mantenimiento(id) ON DELETE SET NULL;


--
-- Name: documentacion fk_documentacion_subido_por_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_subido_por_usuarios FOREIGN KEY (subido_por) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: documentacion fk_documentacion_tipo_documento_id_tipos_documento; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_tipo_documento_id_tipos_documento FOREIGN KEY (tipo_documento_id) REFERENCES control_equipos.tipos_documento(id) ON DELETE RESTRICT;


--
-- Name: documentacion fk_documentacion_verificado_por_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.documentacion
    ADD CONSTRAINT fk_documentacion_verificado_por_usuarios FOREIGN KEY (verificado_por) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: empleados fk_empleados_departamento_id_departamentos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.empleados
    ADD CONSTRAINT fk_empleados_departamento_id_departamentos FOREIGN KEY (departamento_id) REFERENCES control_equipos.departamentos(id) ON DELETE SET NULL;


--
-- Name: equipo_componentes fk_equipo_componentes_equipo_componente_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipo_componentes
    ADD CONSTRAINT fk_equipo_componentes_equipo_componente_id_equipos FOREIGN KEY (equipo_componente_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: equipo_componentes fk_equipo_componentes_equipo_padre_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipo_componentes
    ADD CONSTRAINT fk_equipo_componentes_equipo_padre_id_equipos FOREIGN KEY (equipo_padre_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: equipos fk_equipos_empleado_asignado_id_empleados; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT fk_equipos_empleado_asignado_id_empleados FOREIGN KEY (empleado_asignado_id) REFERENCES control_equipos.empleados(id) ON DELETE SET NULL;


--
-- Name: equipos fk_equipos_estado_id_estados_equipo; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT fk_equipos_estado_id_estados_equipo FOREIGN KEY (estado_id) REFERENCES control_equipos.estados_equipo(id) ON DELETE RESTRICT;


--
-- Name: equipos fk_equipos_marca_id_marcas; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT fk_equipos_marca_id_marcas FOREIGN KEY (marca_id) REFERENCES control_equipos.marcas(id) ON DELETE SET NULL;


--
-- Name: equipos fk_equipos_proveedor_id_proveedores; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT fk_equipos_proveedor_id_proveedores FOREIGN KEY (proveedor_id) REFERENCES control_equipos.proveedores(id) ON DELETE SET NULL;


--
-- Name: equipos fk_equipos_ubicacion_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.equipos
    ADD CONSTRAINT fk_equipos_ubicacion_id_ubicaciones FOREIGN KEY (ubicacion_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE SET NULL;


--
-- Name: inventario_movimientos fk_inventario_movimientos_equipo_asociado_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_equipo_asociado_id_equipos FOREIGN KEY (equipo_asociado_id) REFERENCES control_equipos.equipos(id) ON DELETE SET NULL;


--
-- Name: inventario_movimientos fk_inventario_movimientos_mantenimiento_id_mantenimiento; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_mantenimiento_id_mantenimiento FOREIGN KEY (mantenimiento_id) REFERENCES control_equipos.mantenimiento(id) ON DELETE SET NULL;


--
-- Name: inventario_movimientos fk_inventario_movimientos_tipo_item_id_tipos_item_inventario; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_tipo_item_id_tipos_item_inventario FOREIGN KEY (tipo_item_id) REFERENCES control_equipos.tipos_item_inventario(id) ON DELETE RESTRICT;


--
-- Name: inventario_movimientos fk_inventario_movimientos_ubicacion_destino_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_ubicacion_destino_id_ubicaciones FOREIGN KEY (ubicacion_destino_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE SET NULL;


--
-- Name: inventario_movimientos fk_inventario_movimientos_ubicacion_origen_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_ubicacion_origen_id_ubicaciones FOREIGN KEY (ubicacion_origen_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE SET NULL;


--
-- Name: inventario_movimientos fk_inventario_movimientos_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_movimientos
    ADD CONSTRAINT fk_inventario_movimientos_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: inventario_stock fk_inventario_stock_tipo_item_id_tipos_item_inventario; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_stock
    ADD CONSTRAINT fk_inventario_stock_tipo_item_id_tipos_item_inventario FOREIGN KEY (tipo_item_id) REFERENCES control_equipos.tipos_item_inventario(id) ON DELETE RESTRICT;


--
-- Name: inventario_stock fk_inventario_stock_ubicacion_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.inventario_stock
    ADD CONSTRAINT fk_inventario_stock_ubicacion_id_ubicaciones FOREIGN KEY (ubicacion_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE RESTRICT;


--
-- Name: licencias_software fk_licencias_software_proveedor_id_proveedores; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.licencias_software
    ADD CONSTRAINT fk_licencias_software_proveedor_id_proveedores FOREIGN KEY (proveedor_id) REFERENCES control_equipos.proveedores(id) ON DELETE SET NULL;


--
-- Name: licencias_software fk_licencias_software_software_catalogo_id_software_catalogo; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.licencias_software
    ADD CONSTRAINT fk_licencias_software_software_catalogo_id_software_catalogo FOREIGN KEY (software_catalogo_id) REFERENCES control_equipos.software_catalogo(id) ON DELETE RESTRICT;


--
-- Name: login_logs fk_login_logs_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.login_logs
    ADD CONSTRAINT fk_login_logs_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: mantenimiento fk_mantenimiento_equipo_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.mantenimiento
    ADD CONSTRAINT fk_mantenimiento_equipo_id_equipos FOREIGN KEY (equipo_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: mantenimiento fk_mantenimiento_tecnico_id_tecnicos_mantenimiento; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.mantenimiento
    ADD CONSTRAINT fk_mantenimiento_tecnico_id_tecnicos_mantenimiento FOREIGN KEY (tecnico_id) REFERENCES control_equipos.tecnicos_mantenimiento(id) ON DELETE RESTRICT;


--
-- Name: mantenimiento fk_mantenimiento_tipo_mantenimiento_id_tipos_mantenimiento; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.mantenimiento
    ADD CONSTRAINT fk_mantenimiento_tipo_mantenimiento_id_tipos_mantenimiento FOREIGN KEY (tipo_mantenimiento_id) REFERENCES control_equipos.tipos_mantenimiento(id) ON DELETE RESTRICT;


--
-- Name: movimientos fk_movimientos_autorizado_por_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_autorizado_por_usuarios FOREIGN KEY (autorizado_por) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_confirmado_por_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_confirmado_por_id_usuarios FOREIGN KEY (confirmado_por_id) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_empleado_destino_id_empleados; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_empleado_destino_id_empleados FOREIGN KEY (empleado_destino_id) REFERENCES control_equipos.empleados(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_empleado_receptor_id_empleados; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_empleado_receptor_id_empleados FOREIGN KEY (empleado_receptor_id) REFERENCES control_equipos.empleados(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_equipo_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_equipo_id_equipos FOREIGN KEY (equipo_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: movimientos fk_movimientos_ubicacion_destino_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_ubicacion_destino_id_ubicaciones FOREIGN KEY (ubicacion_destino_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_ubicacion_origen_id_ubicaciones; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_ubicacion_origen_id_ubicaciones FOREIGN KEY (ubicacion_origen_id) REFERENCES control_equipos.ubicaciones(id) ON DELETE SET NULL;


--
-- Name: movimientos fk_movimientos_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT fk_movimientos_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: notificaciones fk_notificaciones_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.notificaciones
    ADD CONSTRAINT fk_notificaciones_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens fk_refresh_tokens_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.refresh_tokens
    ADD CONSTRAINT fk_refresh_tokens_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE CASCADE;


--
-- Name: reportes fk_reportes_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reportes
    ADD CONSTRAINT fk_reportes_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES control_equipos.usuarios(id) ON DELETE CASCADE;


--
-- Name: reservas_equipo fk_reservas_equipo_aprobado_por_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reservas_equipo
    ADD CONSTRAINT fk_reservas_equipo_aprobado_por_id_usuarios FOREIGN KEY (aprobado_por_id) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: reservas_equipo fk_reservas_equipo_equipo_id_equipos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reservas_equipo
    ADD CONSTRAINT fk_reservas_equipo_equipo_id_equipos FOREIGN KEY (equipo_id) REFERENCES control_equipos.equipos(id) ON DELETE CASCADE;


--
-- Name: reservas_equipo fk_reservas_equipo_usuario_solicitante_id_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.reservas_equipo
    ADD CONSTRAINT fk_reservas_equipo_usuario_solicitante_id_usuarios FOREIGN KEY (usuario_solicitante_id) REFERENCES control_equipos.usuarios(id) ON DELETE CASCADE;


--
-- Name: roles_permisos fk_roles_permisos_otorgado_por_usuarios; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles_permisos
    ADD CONSTRAINT fk_roles_permisos_otorgado_por_usuarios FOREIGN KEY (otorgado_por) REFERENCES control_equipos.usuarios(id) ON DELETE SET NULL;


--
-- Name: roles_permisos fk_roles_permisos_permiso_id_permisos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles_permisos
    ADD CONSTRAINT fk_roles_permisos_permiso_id_permisos FOREIGN KEY (permiso_id) REFERENCES control_equipos.permisos(id) ON DELETE CASCADE;


--
-- Name: roles_permisos fk_roles_permisos_rol_id_roles; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.roles_permisos
    ADD CONSTRAINT fk_roles_permisos_rol_id_roles FOREIGN KEY (rol_id) REFERENCES control_equipos.roles(id) ON DELETE CASCADE;


--
-- Name: software_catalogo fk_software_catalogo_marca_id_marcas; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.software_catalogo
    ADD CONSTRAINT fk_software_catalogo_marca_id_marcas FOREIGN KEY (marca_id) REFERENCES control_equipos.marcas(id) ON DELETE SET NULL;


--
-- Name: tecnicos_mantenimiento fk_tecnicos_mantenimiento_proveedor_id_proveedores; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tecnicos_mantenimiento
    ADD CONSTRAINT fk_tecnicos_mantenimiento_proveedor_id_proveedores FOREIGN KEY (proveedor_id) REFERENCES control_equipos.proveedores(id) ON DELETE SET NULL;


--
-- Name: tipos_item_inventario fk_tipos_item_inventario_marca_id_marcas; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT fk_tipos_item_inventario_marca_id_marcas FOREIGN KEY (marca_id) REFERENCES control_equipos.marcas(id) ON DELETE SET NULL;


--
-- Name: tipos_item_inventario fk_tipos_item_inventario_proveedor_preferido_id_proveedores; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.tipos_item_inventario
    ADD CONSTRAINT fk_tipos_item_inventario_proveedor_preferido_id_proveedores FOREIGN KEY (proveedor_preferido_id) REFERENCES control_equipos.proveedores(id) ON DELETE SET NULL;


--
-- Name: ubicaciones fk_ubicaciones_departamento_id_departamentos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.ubicaciones
    ADD CONSTRAINT fk_ubicaciones_departamento_id_departamentos FOREIGN KEY (departamento_id) REFERENCES control_equipos.departamentos(id) ON DELETE SET NULL;


--
-- Name: usuarios fk_usuarios_departamento_id_departamentos; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT fk_usuarios_departamento_id_departamentos FOREIGN KEY (departamento_id) REFERENCES control_equipos.departamentos(id) ON DELETE SET NULL;


--
-- Name: usuarios fk_usuarios_empleado_id_empleados; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT fk_usuarios_empleado_id_empleados FOREIGN KEY (empleado_id) REFERENCES control_equipos.empleados(id) ON DELETE SET NULL;


--
-- Name: usuarios fk_usuarios_rol_id_roles; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.usuarios
    ADD CONSTRAINT fk_usuarios_rol_id_roles FOREIGN KEY (rol_id) REFERENCES control_equipos.roles(id) ON DELETE RESTRICT;


--
-- Name: mantenimiento mantenimiento_estado_equipo_anterior_id_fkey; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.mantenimiento
    ADD CONSTRAINT mantenimiento_estado_equipo_anterior_id_fkey FOREIGN KEY (estado_equipo_anterior_id) REFERENCES control_equipos.estados_equipo(id) ON DELETE RESTRICT;


--
-- Name: movimientos movimientos_empleado_origen_id_fkey; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT movimientos_empleado_origen_id_fkey FOREIGN KEY (empleado_origen_id) REFERENCES control_equipos.empleados(id) ON DELETE SET NULL;


--
-- Name: movimientos movimientos_estado_origen_id_fkey; Type: FK CONSTRAINT; Schema: control_equipos; Owner: -
--

ALTER TABLE ONLY control_equipos.movimientos
    ADD CONSTRAINT movimientos_estado_origen_id_fkey FOREIGN KEY (estado_origen_id) REFERENCES control_equipos.estados_equipo(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

SELECT control_equipos.gestionar_particiones_audit_log();

"""

SEED_SQL = r"""
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_catalogos', 'Administrar catalogos', '96e706b6-0754-5fc6-b717-3c668c4ddfa2');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_inventario_stock', 'Administrar inventario stock', '86ec5ecc-52f3-560b-b9ec-014d8df76342');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_inventario_tipos', 'Administrar inventario tipos', 'f1cdfd24-af99-54b7-9e7f-23d913b2db7a');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_licencias', 'Administrar licencias', '5d169ab9-57c9-57b7-a5a0-dc2597f602db');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_roles', 'Administrar roles', 'd89432ff-1fae-579e-a420-80e60e41e423');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_sistema', 'Administrar sistema', '70a503ca-e151-57d1-bcdb-dc8c0ed0867d');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_software_catalogo', 'Administrar software catalogo', 'e24b3a8b-5998-5748-ae56-c8c17a0f59b5');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('administrar_usuarios', 'Administrar usuarios', '9c297876-bc4c-5e63-9938-dcfbab792d5c');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('aprobar_reservas', 'Aprobar reservas', '7b03d340-ba31-5035-98fa-20aa111586b5');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('asignar_licencias', 'Asignar licencias', 'd3cc480a-9a0b-543b-a330-0f8d7a79293c');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('autorizar_movimientos', 'Autorizar movimientos', 'b4858377-efd5-5de7-8988-48e985fbd793');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('cancelar_movimientos', 'Cancelar movimientos', '183cec72-3abf-5513-8888-1e114d3b9bb2');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('configurar_sistema', 'Configurar sistema', '731c0425-06b2-5da3-b0af-4ab105d1720e');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('crear_equipos', 'Crear equipos', '67031837-3fbe-5908-a3db-e43950907629');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('editar_documentos', 'Editar documentos', 'd4faac62-664a-51d6-b10c-a1f27b06c4a3');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('editar_equipos', 'Editar equipos', 'de4604c7-7082-5cd9-9d88-0077a5ddefc3');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('editar_mantenimientos', 'Editar mantenimientos', '47887a60-dae1-5c3f-93d9-42d37d2513d0');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('editar_movimientos', 'Editar movimientos', '9e52326d-2ea7-58a5-b26c-4f70fd692061');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('eliminar_documentos', 'Eliminar documentos', '67f482a3-6253-5af3-acb0-ae767d3c4bad');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('eliminar_equipos', 'Eliminar equipos', 'f65fcee7-9557-5361-a124-56a7e5a87586');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('eliminar_mantenimientos', 'Eliminar mantenimientos', '5d746b9d-ffba-5ae5-95ed-c464e7f22442');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('generar_reportes', 'Generar reportes', 'cd7fdccf-4d4a-5011-891f-233bec319370');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('gestionar_componentes', 'Gestionar componentes', 'da636de9-c08e-53de-91fe-71e75b224577');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('programar_mantenimientos', 'Programar mantenimientos', '7214f63e-9985-5ec0-a11d-4e015b34d783');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('registrar_movimientos', 'Registrar movimientos', 'e2400dea-9aaf-5cb1-badb-36bd2209740b');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('reservar_equipos', 'Reservar equipos', '06f13f9e-4537-5b5b-8d17-0cb62d85f925');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('subir_documentos', 'Subir documentos', '3b687bd9-b82b-5687-a53a-b8a20a42ddb5');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_auditoria', 'Ver auditoria', '5c85009f-2064-5160-a8d6-11d9c48340af');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_dashboard', 'Ver dashboard', '2d8c3f91-1553-5bb4-bc3e-7deea7af642c');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_documentos', 'Ver documentos', '40de4236-0b27-5817-90fa-190529b42acb');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_equipos', 'Ver equipos', 'a93bb54d-fb41-5cac-be26-2f118ba9413c');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_inventario', 'Ver inventario', '1d6aea81-3466-5b35-9629-7c0d100ecc90');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_licencias', 'Ver licencias', '63671679-dbbe-58a8-874d-d0110c47b7f8');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_mantenimientos', 'Ver mantenimientos', '876f632a-b012-5175-9562-3b08aa2bd416');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_movimientos', 'Ver movimientos', '78236403-6467-5707-816c-4f9ff0c2f4c7');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_proveedores', 'Ver proveedores', '8b0bddc7-fc49-5cc9-b573-b92de61b3b75');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('ver_reservas', 'Ver reservas', '1b390a42-c815-5093-8b3b-5c65caa6b65f');
INSERT INTO control_equipos.permisos (nombre, descripcion, id) VALUES ('verificar_documentos', 'Verificar documentos', '17db8b2f-32e1-565d-85a8-cbfac6589911');
INSERT INTO control_equipos.roles (nombre, descripcion, id) VALUES ('admin', 'Administración completa del sistema', 'd5baeb7e-c22a-5d4d-a277-093a8a111f61');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '96e706b6-0754-5fc6-b717-3c668c4ddfa2');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '86ec5ecc-52f3-560b-b9ec-014d8df76342');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'f1cdfd24-af99-54b7-9e7f-23d913b2db7a');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '5d169ab9-57c9-57b7-a5a0-dc2597f602db');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'd89432ff-1fae-579e-a420-80e60e41e423');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '70a503ca-e151-57d1-bcdb-dc8c0ed0867d');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'e24b3a8b-5998-5748-ae56-c8c17a0f59b5');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '9c297876-bc4c-5e63-9938-dcfbab792d5c');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '7b03d340-ba31-5035-98fa-20aa111586b5');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'd3cc480a-9a0b-543b-a330-0f8d7a79293c');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'b4858377-efd5-5de7-8988-48e985fbd793');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '183cec72-3abf-5513-8888-1e114d3b9bb2');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '731c0425-06b2-5da3-b0af-4ab105d1720e');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '67031837-3fbe-5908-a3db-e43950907629');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'd4faac62-664a-51d6-b10c-a1f27b06c4a3');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'de4604c7-7082-5cd9-9d88-0077a5ddefc3');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '47887a60-dae1-5c3f-93d9-42d37d2513d0');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '9e52326d-2ea7-58a5-b26c-4f70fd692061');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '67f482a3-6253-5af3-acb0-ae767d3c4bad');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'f65fcee7-9557-5361-a124-56a7e5a87586');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '5d746b9d-ffba-5ae5-95ed-c464e7f22442');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'cd7fdccf-4d4a-5011-891f-233bec319370');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'da636de9-c08e-53de-91fe-71e75b224577');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '7214f63e-9985-5ec0-a11d-4e015b34d783');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'e2400dea-9aaf-5cb1-badb-36bd2209740b');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '06f13f9e-4537-5b5b-8d17-0cb62d85f925');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '3b687bd9-b82b-5687-a53a-b8a20a42ddb5');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '5c85009f-2064-5160-a8d6-11d9c48340af');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '2d8c3f91-1553-5bb4-bc3e-7deea7af642c');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '40de4236-0b27-5817-90fa-190529b42acb');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', 'a93bb54d-fb41-5cac-be26-2f118ba9413c');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '1d6aea81-3466-5b35-9629-7c0d100ecc90');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '63671679-dbbe-58a8-874d-d0110c47b7f8');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '876f632a-b012-5175-9562-3b08aa2bd416');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '78236403-6467-5707-816c-4f9ff0c2f4c7');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '8b0bddc7-fc49-5cc9-b573-b92de61b3b75');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '1b390a42-c815-5093-8b3b-5c65caa6b65f');
INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id) VALUES ('d5baeb7e-c22a-5d4d-a277-093a8a111f61', '17db8b2f-32e1-565d-85a8-cbfac6589911');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES ('disponible', 'Disponible', 'Listo para asignación o uso', true, false, false, '#4CAF50', '1b6ce816-7fba-553e-a051-4822bd821c48');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES ('en_uso', 'En Uso', 'Asignado a un empleado o ubicación', true, false, false, '#2196F3', 'd69d97c1-4a83-5478-aa6a-9d82e5a17c82');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES ('prestado', 'Prestado', 'Entregado temporalmente; requiere devolución', false, false, false, '#FF9800', '1c0cf35e-29c2-5b0b-b64e-3242009705cd');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES ('en_mantenimiento', 'En Mantenimiento', 'Mantenimiento en curso', false, false, false, '#FFC107', '20f24b22-d502-58ac-9c48-8a24a426ca52');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'En Reparación', 'En servicio técnico externo', false, false, false, '#FF5722', '3a04d0a8-d2f4-5c21-a82b-fcb67695c89a');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'Averiado', 'Requiere diagnóstico o reparación', false, true, false, '#F44336', '0ce1a7ee-9fee-51cf-8f5a-6eda78564fc0');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'En Cuarentena', 'Bajo evaluación antes de su uso', false, true, false, '#9E9E9E', 'a8a954db-52f8-5ac8-8bca-a80f6f02a3c3');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'Reservado', 'Apartado para un uso específico', false, true, false, '#607D8B', 'bec2e38f-0c67-5593-9436-559602b6c23d');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'En Tránsito', 'En traslado entre ubicaciones', false, false, false, '#795548', '9818e269-ccf8-58bf-b706-2b9cf3d06155');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES (NULL, 'Extraviado', 'Ubicación pendiente de investigación', false, true, false, '#000000', '548fcb95-fcb2-5fec-b125-19509e58e271');
INSERT INTO control_equipos.estados_equipo (codigo, nombre, descripcion, permite_movimientos, requiere_autorizacion, es_estado_final, color_hex, id) VALUES ('dado_de_baja', 'Dado de Baja', 'Retirado definitivamente del servicio', false, true, true, '#E0E0E0', '91282ce7-4afe-5e5b-b0e0-bededcee316e');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Factura Compra', 'Comprobante de adquisición', true, ARRAY['pdf', 'jpg', 'png'], '7674dd8a-21d3-523b-a8c5-28b310bfd51d');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Manual Usuario', 'Instrucciones de operación', false, ARRAY['pdf', 'docx'], 'd876f57f-31db-5a7e-a201-da46526b0d82');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Manual Servicio', 'Instrucciones técnicas de reparación', false, ARRAY['pdf'], '3f62fc43-5f65-5355-b4cb-37bd2c55e6c0');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Ficha Técnica', 'Especificaciones del fabricante', true, ARRAY['pdf'], '59c816ad-b7fa-5040-ba33-638a18c5478e');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Garantía', 'Documento de cobertura de garantía', true, ARRAY['pdf', 'jpg', 'png'], 'b908f73a-78dc-5e53-8051-07e7c053c76a');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Certificado Calibración', 'Resultado de calibración', true, ARRAY['pdf'], '0d7d1cd7-3c20-55a7-ad29-d5e956559ee0');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Reporte Mantenimiento', 'Informe del servicio realizado', false, ARRAY['pdf', 'docx'], '0c1bca7b-b2e6-5a4c-a671-b0c88bcf9954');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Póliza Seguro', 'Cobertura de seguro del equipo', true, ARRAY['pdf'], '93c53410-0486-5e5f-866a-b589d7f95455');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Fotografía', 'Imagen del equipo', false, ARRAY['jpg', 'png', 'webp'], '384e9c8b-7a07-5607-b059-1bb257cd621e');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Acta de Entrega/Recepción', 'Evidencia de entrega o devolución', true, ARRAY['pdf'], '3268c730-96e2-5d9a-814b-78ce40683e01');
INSERT INTO control_equipos.tipos_documento (nombre, descripcion, requiere_verificacion, formato_permitido, id) VALUES ('Informe de Baja', 'Justificación de retiro del activo', true, ARRAY['pdf'], 'aff920aa-01e0-56ef-87b9-59979b992edc');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Preventivo Básico Trimestral', 'Limpieza, inspección y ajustes', 90, false, true, '88540bbd-87d0-5844-a88b-8aff4557e65e');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Preventivo Completo Semestral', 'Revisión y pruebas de funcionamiento', 180, true, true, 'fd18e7e3-388a-5d9c-89ec-2527821832b8');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Preventivo Anual', 'Revisión según fabricante', 365, true, true, '5a5d2a96-a656-5329-bb15-6b02398f8398');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Correctivo Menor', 'Reparación de una falla simple', NULL, true, false, '78eeeaa2-2593-584b-ab86-ad740f83cea0');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Correctivo Mayor', 'Reparación de una falla compleja', NULL, true, false, '28a81597-4bb2-5df3-a476-32ecd55b815d');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Calibración Anual', 'Verificación y ajuste de precisión', 365, true, true, '72d68d6e-72e8-5465-93eb-44ca772b4e0c');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Actualización Firmware/Software', 'Actualización de versiones', NULL, true, false, '1ab7beb4-d2ed-5e3c-b0d7-165b61657fba');
INSERT INTO control_equipos.tipos_mantenimiento (nombre, descripcion, periodicidad_dias, requiere_documentacion, es_preventivo, id) VALUES ('Inspección de Seguridad', 'Verificación de condiciones de seguridad', 120, true, true, '5af99743-e8b6-53f3-8adc-8f1fc851b020');
INSERT INTO control_equipos.ubicaciones (nombre, is_active, id) VALUES ('Almacén de informática', true, 'ee2312ca-0766-5935-90d6-dd2577f57b2e');
INSERT INTO control_equipos.configuracion_empresa (id, nombre) VALUES (1, 'ControlEquipos');
REFRESH MATERIALIZED VIEW control_equipos.mv_equipos_estado;
REFRESH MATERIALIZED VIEW control_equipos.mv_mantenimientos_proximos;
"""


def upgrade():
    op.execute(text(SCHEMA_SQL))
    op.execute(text(SEED_SQL))


def downgrade():
    raise RuntimeError("La versión inicial no se elimina mediante downgrade. Restaure un respaldo en una base vacía o use la inicialización explícita con respaldo.")

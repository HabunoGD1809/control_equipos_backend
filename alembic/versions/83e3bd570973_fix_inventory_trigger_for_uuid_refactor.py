"""Fix inventory trigger for UUID refactor

Revision ID: 83e3bd570973
Revises: 89c1f03dae28
Create Date: 2026-03-12 17:09:15.053335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '83e3bd570973'
down_revision: Union[str, None] = '89c1f03dae28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Actualiza la función del trigger para usar UUIDs."""
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_inventario_stock_fn()
    RETURNS TRIGGER AS $$
    DECLARE
        v_ubicacion_id UUID;
        v_cantidad_ajuste INTEGER;
        v_lote_final TEXT;
    BEGIN
        -- 1. DETERMINAR SI ES ENTRADA O SALIDA
        -- Tipos que SUMAN al stock (usan ubicacion_destino_id)
        IF NEW.tipo_movimiento IN ('Entrada Compra', 'Ajuste Positivo', 'Transferencia Entrada', 'Devolucion Interna') THEN
            v_ubicacion_id := NEW.ubicacion_destino_id;
            v_cantidad_ajuste := NEW.cantidad;
            v_lote_final := COALESCE(NEW.lote_destino, 'N/A');
            
        -- Tipos que RESTAN al stock (usan ubicacion_origen_id)
        ELSIF NEW.tipo_movimiento IN ('Salida Uso', 'Salida Descarte', 'Ajuste Negativo', 'Transferencia Salida', 'Devolucion Proveedor') THEN
            v_ubicacion_id := NEW.ubicacion_origen_id;
            v_cantidad_ajuste := -NEW.cantidad;
            v_lote_final := COALESCE(NEW.lote_origen, 'N/A');
        END IF;

        -- 2. SI HAY UNA UBICACIÓN VÁLIDA, PROCEDER CON EL UPSERT
        IF v_ubicacion_id IS NOT NULL THEN
            INSERT INTO control_equipos.inventario_stock (
                tipo_item_id, ubicacion_id, lote, cantidad_actual, ultima_actualizacion
            )
            VALUES (
                NEW.tipo_item_id, v_ubicacion_id, v_lote_final, NEW.cantidad, NOW()
            )
            ON CONFLICT (tipo_item_id, ubicacion_id, lote) 
            DO UPDATE SET 
                cantidad_actual = control_equipos.inventario_stock.cantidad_actual + v_cantidad_ajuste,
                ultima_actualizacion = NOW();

            -- 3. VALIDACIÓN DE SEGURIDAD: No permitir stock negativo tras la operación
            IF (SELECT cantidad_actual FROM control_equipos.inventario_stock 
                WHERE tipo_item_id = NEW.tipo_item_id AND ubicacion_id = v_ubicacion_id 
                AND lote = v_lote_final) < 0 THEN
                RAISE EXCEPTION 'Error al actualizar stock: Stock insuficiente en la ubicación seleccionada.';
            END IF;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Downgrade schema: No es necesario revertir el trigger a una versión rota."""
    pass

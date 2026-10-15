import os,sys,asyncio,io,json,time,logging
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from uuid import uuid4
import argparse
BACK=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Verifica los flujos completos en una base de pruebas aislada.')
parser.add_argument('--database',required=True,help='Base existente y migrada; su nombre debe contener test')
parser.add_argument('--host',default='127.0.0.1')
parser.add_argument('--port',default='5433')
parser.add_argument('--output',type=Path,default=BACK/'verification')
args=parser.parse_args()
if 'test' not in args.database.lower():
 parser.error('No se permite ejecutar esta verificación sobre una base de producción.')
OUTPUT=args.output.resolve();OUTPUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(BACK));os.chdir(BACK)
os.environ.update(POSTGRES_SERVER=args.host,POSTGRES_PORT=args.port,POSTGRES_DB=args.database,REPORT_EXECUTION_MODE='background',UPLOADS_DIRECTORY=str(OUTPUT/'uploads'))
from app.main import app
from app.db.session import SessionLocal
from app.models import EstadoEquipo,Usuario,Notificacion
from app.core.config import settings
from app.core.password import get_password_hash,verify_password
from app.core.event_broker import broker
from sqlalchemy import select,text
from httpx import AsyncClient,ASGITransport
from scripts.bootstrap import bootstrap
from PIL import Image
logging.getLogger().setLevel(logging.ERROR)
results=[]
def record(name):results.append(name);print('OK:',name,flush=True)
async def main():
 password='Aa1!'+uuid4().hex
 username='qa_'+uuid4().hex[:8]
 with SessionLocal() as db:
  user=bootstrap(db,username,f'{username}@example.com',password)
  user_id=user.id
  available=db.scalar(select(EstadoEquipo).where(EstadoEquipo.nombre=='Disponible')).id
 async with app.router.lifespan_context(app):
  async with AsyncClient(transport=ASGITransport(app=app),base_url='http://testserver',timeout=60) as client:
   async def call(method,path,data=None,expected=200,**kwargs):
    response=await client.request(method,'/api/v1'+path,json=data,**kwargs)
    if response.status_code!=expected:
     raise AssertionError(f'{method} {path}: {response.status_code}: {response.text[:700]}')
    return response.json() if response.content and 'json' in response.headers.get('content-type','') else response
   token=await client.post('/api/v1/auth/login/access-token',data={'username':username,'password':password})
   assert token.status_code==200,token.text[:120]
   client.headers['Authorization']='Bearer '+token.json()['access_token']
   me=await call('GET','/usuarios/me');assert me['id']==str(user_id)
   await call('GET','/notificaciones/',expected=403)
   old_tokens=token.json();new_password='Aa2!'+uuid4().hex
   await call('POST','/auth/change-password',{'current_password':password,'new_password':new_password},204)
   await call('GET','/usuarios/me',expected=401)
   await call('POST','/auth/refresh-token',{'refresh_token':old_tokens['refresh_token']},403)
   token=await client.post('/api/v1/auth/login/access-token',data={'username':username,'password':new_password})
   assert token.status_code==200
   client.headers['Authorization']='Bearer '+token.json()['access_token']
   record('Administrador: creación, permisos e inicio de sesión')
   for suffix in ['/equipos/','/inventario/tipos/','/inventario/stock/','/movimientos/','/reservas/','/empleados/','/ubicaciones/','/reportes/historial','/notificaciones/']:
    await call('GET',suffix)
   record('Listados principales accesibles')
   await call('PUT','/empresa/',{'nombre':'Informática QA Álvarez','email':'qa@example.com','identificacion':'QA-2026'})
   img=Image.new('RGB',(300,100),(23,50,77));buffer=io.BytesIO();img.save(buffer,'PNG')
   response=await client.post('/api/v1/empresa/logo',files={'file':('logo.png',buffer.getvalue(),'image/png')});assert response.status_code==200,response.text[:300]
   branding=await call('GET','/empresa/publica');assert branding['nombre']=='Informática QA Álvarez'
   await call('GET','/empresa/publica/logo')
   record('Empresa y logo: almacenamiento y consulta pública')
   origin=await call('POST','/ubicaciones/',{'nombre':'Origen '+uuid4().hex[:8]},201)
   dest=await call('POST','/ubicaciones/',{'nombre':'Destino '+uuid4().hex[:8]},201)
   employee=await call('POST','/empleados/',{'nombre_completo':'Custodio QA '+uuid4().hex[:6],'email':uuid4().hex[:8]+'@example.com'},201)
   await call('GET','/empleados/'+employee['id']);await call('GET','/ubicaciones/'+origin['id'])
   item=await call('POST','/inventario/tipos/',{'nombre':'Tóner QA '+uuid4().hex[:8],'categoria':'Consumible','unidad_medida':'Unidad','color':'Cian','tecnologia':'Tóner','rendimiento_paginas':3000,'modelos_equipo_compatibles':['M404','M428'],'es_original':True},201)
   assert item['color']=='Cian' and item['rendimiento_paginas']==3000
   await call('POST','/inventario/movimientos/',{'tipo_item_id':item['id'],'tipo_movimiento':'Entrada Compra','cantidad':10,'ubicacion_destino_id':origin['id'],'costo_unitario':'25.5000'},201)
   await call('POST','/inventario/movimientos/',{'tipo_item_id':item['id'],'tipo_movimiento':'Salida Uso','cantidad':5,'ubicacion_origen_id':origin['id']},201)
   await call('POST','/inventario/movimientos/',{'tipo_item_id':item['id'],'tipo_movimiento':'Transferencia Salida','cantidad':3,'ubicacion_origen_id':origin['id'],'ubicacion_destino_id':dest['id']},201)
   stocks=await call('GET','/inventario/stock/',params={'tipo_item_id':item['id']});assert sorted(s['cantidad_actual'] for s in stocks)==[2,3],stocks
   await call('POST','/inventario/movimientos/',{'tipo_item_id':item['id'],'tipo_movimiento':'Salida Uso','cantidad':3,'ubicacion_origen_id':origin['id']},409)
   stocks2=await call('GET','/inventario/stock/',params={'tipo_item_id':item['id']});assert sum(s['cantidad_actual'] for s in stocks2)==5
   await call('DELETE','/inventario/tipos/'+item['id'],expected=409)
   origin_stock=next(row for row in stocks2 if row['ubicacion_id']==origin['id'])
   await call('PUT','/inventario/stock/'+origin_stock['id']+'/details',{'lote':'CORREGIDO'},409)
   await call('POST','/inventario/movimientos/',{'tipo_item_id':item['id'],'tipo_movimiento':'Transferencia Salida','cantidad':2,'ubicacion_origen_id':origin['id'],'ubicacion_destino_id':origin['id'],'lote_origen':'N/A','lote_destino':'CORREGIDO'},201)
   corrected=await call('GET','/inventario/stock/',params={'tipo_item_id':item['id']})
   assert sum(row['cantidad_actual'] for row in corrected)==5
   assert any(row['lote']=='CORREGIDO' and row['cantidad_actual']==2 for row in corrected)
   record('Tóner: atributos, entradas, consumos, transferencia y protección de saldos')
   equipment=await call('POST','/equipos/',{'nombre':'Portátil QA','numero_serie':'QA-'+uuid4().hex[:6].upper()+'-TEST','estado_id':str(available),'ubicacion_id':origin['id']},201)
   child=await call('POST','/equipos/',{'nombre':'Componente QA','numero_serie':'QA-'+uuid4().hex[:6].upper()+'-PART','estado_id':str(available),'ubicacion_id':origin['id']},201)
   await call('POST','/equipos/'+equipment['id']+'/componentes',{'equipo_componente_id':child['id'],'cantidad':1,'tipo_relacion':'componente'},201)
   await call('POST','/equipos/'+child['id']+'/componentes',{'equipo_componente_id':equipment['id'],'cantidad':1,'tipo_relacion':'componente'},409)
   await call('POST','/movimientos/',{'equipo_id':child['id'],'tipo_movimiento':'Transferencia Bodega','ubicacion_destino_id':dest['id']},409)
   move=await call('POST','/movimientos/',{'equipo_id':equipment['id'],'tipo_movimiento':'Asignacion Interna','ubicacion_origen_id':origin['id'],'ubicacion_destino_id':dest['id'],'empleado_destino_id':employee['id']},201)
   assert move['empleado_destino_id']==employee['id'] and move['estado']=='En Proceso',move
   await call('PATCH','/movimientos/'+move['id']+'/estado',{'estado':'Completado'})
   assert move['equipos_incluidos']==2
   part=await call('GET','/equipos/'+child['id']);assert part['empleado_asignado_id']==employee['id'] and part['ubicacion_id']==dest['id']
   eq=await call('GET','/equipos/'+equipment['id']);assert eq['empleado_asignado_id']==employee['id'],eq
   await call('DELETE','/equipos/'+equipment['id'],expected=409)
   await call('POST','/movimientos/',{'equipo_id':equipment['id'],'tipo_movimiento':'Entrada','ubicacion_origen_id':dest['id'],'ubicacion_destino_id':origin['id']},201)
   eq=await call('GET','/equipos/'+equipment['id']);assert not eq['empleado_asignado_id'] and eq['estado']['nombre']=='Disponible'
   move=await call('POST','/movimientos/',{'equipo_id':equipment['id'],'tipo_movimiento':'Transferencia Bodega','ubicacion_origen_id':origin['id'],'ubicacion_destino_id':dest['id']},201)
   await call('POST','/movimientos/'+move['id']+'/cancelar',{})
   eq=await call('GET','/equipos/'+equipment['id']);assert eq['ubicacion_id']==origin['id'] and eq['estado']['nombre']=='Disponible'
   part=await call('GET','/equipos/'+child['id']);assert part['ubicacion_id']==origin['id'] and part['estado']['nombre']=='Disponible'
   child_history=await call('GET','/movimientos/',params={'equipo_id':child['id']});assert len(child_history)>=3
   record('Activos: custodio, recepción, devolución, cancelación e historial protegido')
   start=datetime.now(timezone.utc)+timedelta(days=1)
   reservation=await call('POST','/reservas/',{'equipo_id':equipment['id'],'fecha_hora_inicio':start.isoformat(),'fecha_hora_fin':(start+timedelta(hours=2)).isoformat(),'proposito':'Comprobación de entrega'},201)
   reservation=await call('PATCH','/reservas/'+reservation['id']+'/check-in-out',{'check_out_time':datetime.now(timezone.utc).isoformat()});assert reservation['estado']=='En Curso'
   eq=await call('GET','/equipos/'+equipment['id']);assert eq['estado']['nombre']=='Prestado'
   reservation=await call('PATCH','/reservas/'+reservation['id']+'/check-in-out',{'check_in_time':datetime.now(timezone.utc).isoformat(),'notas_devolucion':'Sin daños'});assert reservation['estado']=='Finalizada'
   part=await call('GET','/equipos/'+child['id']);assert part['estado']['nombre']=='Disponible'
   record('Reservas: entrega, bloqueo durante préstamo y devolución')
   technician=await call('POST','/tecnicos/',{'nombre_completo':'Técnico QA '+uuid4().hex[:8]},201)
   maintenance_type=await call('POST','/catalogos/tipos-mantenimiento/',{'nombre':'Preventivo QA '+uuid4().hex[:8],'es_preventivo':True,'periodicidad_dias':90},201)
   maintenance=await call('POST','/mantenimientos/',{'equipo_id':equipment['id'],'tecnico_id':technician['id'],'tipo_mantenimiento_id':maintenance_type['id'],'estado':'Programado'},201)
   await call('PUT','/mantenimientos/'+maintenance['id'],{'estado':'En Proceso'})
   part=await call('GET','/equipos/'+child['id']);assert part['estado']['nombre']=='En Mantenimiento'
   await call('POST','/movimientos/',{'equipo_id':equipment['id'],'tipo_movimiento':'Transferencia Bodega','ubicacion_destino_id':dest['id']},409)
   completed=await call('PUT','/mantenimientos/'+maintenance['id'],{'estado':'Completado','observaciones':'Revisión y limpieza; pruebas satisfactorias.'})
   assert completed['fecha_finalizacion'] and completed['fecha_proximo_mantenimiento']
   part=await call('GET','/equipos/'+child['id']);assert part['estado']['nombre']=='Disponible'
   await call('DELETE','/mantenimientos/'+maintenance['id'],expected=409)
   record('Mantenimiento y conjuntos: bloqueo, restauración, próxima fecha e historial')
   concurrency_item=await call('POST','/inventario/tipos/',{'nombre':'Concurrencia QA '+uuid4().hex[:8],'categoria':'Consumible','unidad_medida':'Unidad'},201)
   await call('POST','/inventario/movimientos/',{'tipo_item_id':concurrency_item['id'],'tipo_movimiento':'Entrada Compra','cantidad':10,'ubicacion_destino_id':origin['id']},201)
   outgoing={'tipo_item_id':concurrency_item['id'],'tipo_movimiento':'Salida Uso','cantidad':8,'ubicacion_origen_id':origin['id']}
   attempts=await asyncio.gather(client.post('/api/v1/inventario/movimientos/',json=outgoing),client.post('/api/v1/inventario/movimientos/',json=outgoing))
   assert sorted(r.status_code for r in attempts)==[201,409],[(r.status_code,r.text[:120]) for r in attempts]
   final_stock=await call('GET','/inventario/stock/',params={'tipo_item_id':concurrency_item['id']});assert sum(x['cantidad_actual'] for x in final_stock)==2
   record('Consumos concurrentes: no se permite sobregirar el stock')
   # Direct committed DB inserts must reach the process without a shared in-memory broker.
   await asyncio.sleep(1)
   queue=broker.subscribe(str(user_id));t=time.monotonic()
   with SessionLocal() as db:
    db.add(Notificacion(usuario_id=user_id,mensaje='Señal QA',tipo='info',urgencia=0));db.commit()
   await asyncio.wait_for(queue.get(),5);elapsed=time.monotonic()-t;broker.unsubscribe(str(user_id),queue)
   assert elapsed<3,elapsed
   record(f'Notificación PostgreSQL entre sesiones: {elapsed:.2f} segundos')
   software=await call('POST','/licencias/catalogo',{'nombre':'Software QA '+uuid4().hex[:8],'tipo_licencia':'Perpetua','metrica_licenciamiento':'Por Dispositivo'},201)
   license=await call('POST','/licencias/',{'software_catalogo_id':software['id'],'fecha_adquisicion':date.today().isoformat(),'cantidad_total':2,'clave_producto':'QA-NO-ES-UNA-CLAVE-REAL','costo_adquisicion':'150.00'},201)
   assert license['cantidad_disponible']==2
   files=[]
   for report_type in ['equipos','mantenimientos','movimientos','auditoria','inventario','kardex','licencias']:
    for format_ in ['pdf','excel','csv']:
     response=await call('POST','/reportes/',{'tipo_reporte':report_type,'formato':format_,'fecha_inicio':date.today().isoformat(),'fecha_fin':date.today().isoformat()})
     file=await call('GET','/reportes/'+response['reporte_id']+'/download')
     assert len(file.content)>10
     folder=OUTPUT/'reports';folder.mkdir(exist_ok=True)
     ext='xlsx' if format_=='excel' else format_;(folder/f'{report_type}.{ext}').write_bytes(file.content)
     files.append(f'{report_type}.{ext}')
   record('21 reportes descargables: siete módulos en PDF, Excel y CSV')
   tokens=token.json()
   rotated=await call('POST','/auth/refresh-token',{'refresh_token':tokens['refresh_token']});assert tokens['refresh_token']!=rotated['refresh_token']
   await call('POST','/auth/refresh-token',{'refresh_token':tokens['refresh_token']},403)
   record('Rotación de sesión y rechazo de reutilización del token')
 (OUTPUT/'integration-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())

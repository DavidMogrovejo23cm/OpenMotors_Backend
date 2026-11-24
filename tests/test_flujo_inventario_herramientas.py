from sqlalchemy.orm import Session
from sqlalchemy import select, func
from tests.test_permisos import api
from app.modules.taller.models import Registro, Presupuesto, ItemPresupuesto
from app.modules.inventario.models import Producto, MovimientoKardex

def request_ok(client, method, path, headers, data=None, expected=(200,201)):
    result=client.request(method,path,headers=headers,json=data)
    assert result.status_code in expected, (path,result.status_code,result.text)
    return result.json() if result.content else None

def approved_job(engine):
    with Session(engine) as db:
        p=db.get(Presupuesto,1);p.estado="APROBADO_TOTAL";p.total_presupuestado=10;p.total_aprobado=10
        db.add(ItemPresupuesto(id_presupuesto=1,tipo_item="REPUESTO",id_producto=1,descripcion="Filtro",cantidad=1,precio_unitario=10,subtotal=10,estado_aprobacion="APROBADO"))
        db.commit()

def test_retirar_reintentar_facturar_y_cobrar_no_duplica_el_consumo(api):
    client,h,engine=api;approved_job(engine)
    request_ok(client,"PUT","/api/usuarios/2/permisos",h[1],{"permisos":["inventario_consumos"]})
    request_ok(client,"POST","/api/reservas/presupuesto/1",h[2])
    reserves=client.get("/api/reservas/registro/1",headers=h[2]).json();res_id=reserves[0]["id_reserva"]
    for _ in range(2):request_ok(client,"POST",f"/api/reservas/{res_id}/retirar",h[2])
    request_ok(client,"POST","/api/reservas/presupuesto/1",h[2])
    assert len(client.get("/api/reservas/registro/1",headers=h[2]).json())==1
    request_ok(client,"POST","/api/detalles-factura",h[1],{"id_factura":1,"id_producto":1,"cantidad":1})
    note=request_ok(client,"POST","/api/notas-venta/preparar",h[1],{"id_registro":1,"tarifa_hora_mecanico":0})
    request_ok(client,"POST",f"/api/notas-venta/{note['id_nota_venta']}/confirmar-pago",h[1],{"monto":10,"id_operacion":"cobro"})
    with Session(engine) as db:
        assert db.get(Producto,1).stock==9
        assert db.get(Producto,1).stock_reservado==0
        assert db.scalar(select(func.count()).select_from(MovimientoKardex).where(MovimientoKardex.tipo_movimiento=="SALIDA"))==1

def test_escanear_antes_de_retirar_y_repetir_operacion_es_seguro(api):
    client,h,engine=api;approved_job(engine)
    payload={"codigo_barras":"123456789","cantidad":1,"id_registro":1,"id_operacion":"lectura-1","motivo":"Instalación"}
    for _ in range(2):request_ok(client,"POST","/api/kardex/salida",h[1],payload)
    assert client.post("/api/kardex/salida",headers=h[1],json={**payload,"cantidad":2}).status_code==409
    request_ok(client,"POST","/api/reservas/presupuesto/1",h[1])
    reserva=client.get("/api/reservas/registro/1",headers=h[1]).json()[0]
    result=request_ok(client,"POST",f"/api/reservas/{reserva['id_reserva']}/retirar",h[1])
    assert result["movimiento_kardex"] is None
    assert client.get("/api/productos/1",headers=h[1]).json()["stock"]==9

def test_stock_reservado_y_devoluciones_no_se_pueden_duplicar(api):
    client,h,engine=api
    with Session(engine) as db:db.get(Producto,1).stock_reservado=10;db.commit()
    payload={"codigo_barras":"123456789","cantidad":1,"id_registro":1,"id_operacion":"sin-stock"}
    assert client.post("/api/kardex/salida",headers=h[1],json=payload).status_code==400
    with Session(engine) as db:db.get(Producto,1).stock_reservado=0;db.commit()
    request_ok(client,"POST","/api/kardex/salida",h[1],{**payload,"cantidad":2,"id_operacion":"dos"})
    refund={"codigo_barras":"123456789","cantidad":1,"id_registro":1,"origen":"DEVOLUCION_TALLER","id_operacion":"devolucion"}
    for _ in range(2):request_ok(client,"POST","/api/kardex/entrada",h[1],refund)
    assert client.post("/api/kardex/entrada",headers=h[1],json={**refund,"cantidad":2,"id_operacion":"exceso"}).status_code==400
    assert client.get("/api/productos/1",headers=h[1]).json()["stock"]==9

def test_codigo_de_barras_unico_y_ajuste_auditado(api):
    client,h,engine=api
    assert client.post("/api/productos",headers=h[1],json={"codigo_personal":"OTRO","codigo_barras":"123456789","nombre":"Duplicado","id_categoria":1}).status_code==409
    result=request_ok(client,"PUT","/api/productos/1",h[1],{"nombre":"Filtro nuevo","stock":12})
    assert result["nombre"]=="Filtro nuevo" and result["stock"]==12
    assert client.delete("/api/productos/1",headers=h[1]).status_code==409
    assert any(m["origen"]=="AJUSTE_CATALOGO" for m in client.get("/api/kardex/movimientos",headers=h[1]).json())

def test_herramientas_registro_edicion_consulta_y_permisos(api):
    client,h,_=api
    payload={"codigo":" h-01 ","nombre":"Torquímetro","estado":"DISPONIBLE","ubicacion":"Banco 1"}
    tool=request_ok(client,"POST","/api/herramientas",h[1],payload)
    assert tool["codigo"]=="H-01"
    assert client.post("/api/herramientas",headers=h[1],json=payload).status_code==409
    request_ok(client,"PUT",f"/api/herramientas/{tool['id_herramienta']}",h[1],{**payload,"estado":"MANTENIMIENTO"})
    assert client.get("/api/herramientas",headers=h[2]).json()[0]["estado"]=="MANTENIMIENTO"
    assert client.post("/api/herramientas",headers=h[2],json=payload).status_code==403
    assert client.get("/api/herramientas",headers=h[4]).status_code==403

def test_recorrido_integrado_hasta_la_entrega_y_portal_del_cliente(api):
    client,h,engine=api
    reg=request_ok(client,"POST","/api/registros",h[1],{"id_vehiculo":1,"id_encargado":2,"flujo_integrado":True})
    rid=reg["id_registro"]
    diagnostic={"id_registro":rid,"id_vehiculo":1,"id_mecanico":2,"origen_diagnostico":"CRITERIO_TECNICO","observaciones_generales":"Frenos","detalles":[{"sistema":"FRENOS","parte":"Pastillas","estado":"MALO"}]}
    assert client.post("/api/diagnosticos",headers=h[2],json=diagnostic).status_code==400
    rec=request_ok(client,"POST","/api/recepciones",h[1],{"id_registro":rid,"id_vehiculo":1,"kilometraje":1000,"foto_frente":"/static/frente.png","foto_posterior":"/static/atras.png","foto_lateral_izq":"/static/izq.png","foto_lateral_der":"/static/der.png","firma_cliente":"/static/firma.png","crear_orden_automatica":False})
    assert rec["completa"]
    request_ok(client,"POST","/api/diagnosticos",h[2],diagnostic)
    budget=request_ok(client,"POST","/api/presupuestos",h[1],{"id_registro":rid,"id_vehiculo":1,"id_usuario":4,"items":[{"tipo_item":"REPUESTO","id_producto":1,"descripcion":"Filtro","cantidad":1,"precio_unitario":10},{"tipo_item":"MANO_OBRA","descripcion":"Instalación","cantidad":1,"precio_unitario":20}]})
    request_ok(client,"POST",f"/api/presupuestos/{budget['id_presupuesto']}/enviar",h[1])
    assert client.post(f"/api/presupuestos/{budget['id_presupuesto']}/decision",headers=h[5],json={"decision":"APROBADO_TOTAL"}).status_code==404
    request_ok(client,"POST",f"/api/presupuestos/{budget['id_presupuesto']}/decision",h[4],{"decision":"APROBADO_TOTAL"})
    assert client.post("/api/reparaciones/control-calidad",headers=h[2],json={"id_registro":rid,"paso_inspeccion":True}).status_code==400
    request_ok(client,"PUT","/api/usuarios/2/permisos",h[1],{"permisos":["inventario_consumos"]})
    request_ok(client,"POST",f"/api/reservas/presupuesto/{budget['id_presupuesto']}",h[2])
    reserve=client.get(f"/api/reservas/registro/{rid}",headers=h[2]).json()[0]
    request_ok(client,"POST",f"/api/reservas/{reserve['id_reserva']}/retirar",h[2])
    request_ok(client,"POST","/api/reparaciones/bitacora",h[2],{"id_registro":rid,"descripcion_trabajo":"Filtro instalado y probado","horas_trabajadas":1})
    request_ok(client,"POST","/api/reparaciones/control-calidad",h[2],{"id_registro":rid,"paso_inspeccion":True,"observaciones":"Prueba correcta"})
    assert client.post("/api/entregas",headers=h[1],json={"id_registro":rid,"persona_recibe":"Cliente"}).status_code==400
    note=request_ok(client,"POST","/api/notas-venta/preparar",h[1],{"id_registro":rid,"tarifa_hora_mecanico":0})
    assert note["total"]==30
    request_ok(client,"POST",f"/api/registros/{rid}/pagos",h[1],{"monto":30,"id_operacion":"pago-integrado"})
    delivered=request_ok(client,"POST","/api/entregas",h[1],{"id_registro":rid,"persona_recibe":"Cliente","firma_cliente_entrega":"/static/firma.png","kilometraje_salida":1001})
    assert delivered["estado_orden"]==3
    view=request_ok(client,"GET",f"/api/registros/{rid}/flujo",h[4])
    assert view["entrega"]["persona_recibe"]=="Cliente"
    assert len(view["registro"]["detalles"])==2
    assert client.get("/api/productos/1",headers=h[1]).json()["stock"]==9
    assert client.get(f"/api/registros/{rid}/flujo",headers=h[5]).status_code==404

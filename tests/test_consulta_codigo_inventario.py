"""RF-61/62/63: una lectura del teléfono identifica; no confirma movimientos."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from urllib.parse import quote

from tests.test_permisos import api
from app.modules.inventario.models import Producto, MovimientoKardex


@pytest.mark.parametrize('codigo', ['0012345678905', '7861009876543', 'REP-0007-A'])
def test_identificar_etiqueta_repetidamente_no_cambia_el_stock(api, codigo):
    c, h, engine = api
    created = c.post('/api/productos', headers=h[1], json={
        'codigo_personal': 'SCAN-TEST', 'codigo_barras': codigo,
        'nombre': 'Repuesto para escaneo', 'id_categoria': 1, 'stock': 5,
    })
    assert created.status_code == 201, created.text
    pid = created.json()['id_producto']
    with Session(engine) as db:
        initial_movements = db.scalar(select(func.count()).select_from(MovimientoKardex))
    for _ in range(5):
        read = c.get('/api/kardex/escanear/' + quote(codigo, safe=''), headers=h[1])
        assert read.status_code == 200, read.text
        assert read.json()['encontrado'] is True
        assert read.json()['producto']['id_producto'] == pid
        assert read.json()['producto']['codigo_barras'] == codigo
    unknown = c.get('/api/kardex/escanear/DESCONOCIDO-999', headers=h[1])
    assert unknown.status_code == 200 and unknown.json()['encontrado'] is False
    with Session(engine) as db:
        assert db.get(Producto, pid).stock == 5
        assert db.scalar(select(func.count()).select_from(MovimientoKardex)) == initial_movements

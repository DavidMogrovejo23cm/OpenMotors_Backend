# Permisos del servidor

La política está en app/core/access_policy.py y se añade como dependencia a todos
los routers del API, incluidas sus rutas alternativas. Una acción nueva no está
permitida a mecánicos/clientes hasta tener una regla explícita. Los roles activos
y las autorizaciones se leen de la base en cada petición, nunca desde el JWT,
el almacenamiento del navegador o la descripción del perfil.

| Actor | Acceso |
| --- | --- |
| ADMIN | Administración completa; único que asigna roles, mecánicos, cobros y pagos del personal. |
| MECANICO | Órdenes asignadas y datos necesarios de sus clientes/carros; diagnóstico, bitácora, evidencias y calidad de esas órdenes. No entrega, cobra, reasigna personal ni responde por el cliente. |
| CLIENTE | Sus carros, órdenes, diagnósticos, evidencias, historial, comprobantes y presupuestos. Puede responder un presupuesto propio enviado, actualizar sus datos personales, foto y kilometraje. No registra carros ni administra inventario. |

Autorizaciones adicionales para mecánicos, desactivadas por defecto:

- recepcion: alta de clientes y carros, actualización de datos de recepción.
  No permite cambiar credenciales del cliente ni administrar cuentas del personal.
  Para registrar una recepción técnica debe existir una orden asignada.
- inventario_entradas: alta/edición de productos, categorías, entradas y proveedores.
- inventario_consumos: reserva y salida de repuestos vinculados a sus órdenes.

GET/PUT /api/usuarios/{id}/permisos consulta/guarda la lista de autorizaciones.
Solo ADMIN puede concederlas. El usuario puede consultar las propias.
Las autorizaciones antiguas PERMISOS:... y las guardadas en localStorage ya no
se consideran válidas. El administrador debe conceder las adicionales de forma
explícita desde Perfiles; no se convierten automáticamente en privilegios nuevos.
La tabla permisos_usuario se crea durante la inicialización habitual del backend.
La revocación se aplica a la siguiente petición, sin necesidad de cerrar sesión.

Las consultas por propietario/asignación están en app/core/access_scope.py.
Se aplican antes de consultar la base, también en listados, búsquedas y rutas
alternativas. Las referencias enviadas en el cuerpo se comprueban contra ese
alcance y el autor de movimientos y controles se obtiene de la sesión.
Los recibos del cliente no muestran márgenes, remuneraciones ni costos internos.
Las métricas, campañas, finanzas generales y la creación de cuentas requieren ADMIN.

Este bloque protege las operaciones y datos del API. Los archivos que ya se sirven
con URLs públicas siguen siendo públicos; privatizar el almacenamiento y emitir
accesos temporales requiere el bloque de archivos privados antes de producción.
También se retiró del frontend una credencial fija en un acceso Google sin uso.
Cambiar la contraseña de la cuenta asociada antes de publicar; retirarla del
código no invalida una contraseña que ya esté configurada en una base existente.

Validación: pruebas HTTP con bases aisladas para los tres roles, acceso a datos
ajenos, autoría, acciones prohibidas, concesión/revocación y suspensión de roles.
No se han cambiado roles ni contraseñas en una base de producción.

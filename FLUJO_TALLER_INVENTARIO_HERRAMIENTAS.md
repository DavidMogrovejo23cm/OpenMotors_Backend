# Flujo del taller, inventario y herramientas

## Pantallas y operación

- `/registros`: crear una orden abre `/ordenes/:id`. Las órdenes nuevas usan el flujo integrado.
- `/ordenes/:id`: recepción, diagnóstico, presupuesto, reparación, calidad, cobro y entrega.
- `/inventario/escaneo`: búsqueda por código, confirmación de entrada/salida y consulta del historial.
- `/herramientas`: consulta del catálogo; administración permite registrar y actualizar.

La recepción recoge cuatro fotos y firma dibujada y guardada. El diagnóstico registra sistemas revisados y origen técnico/escáner. El presupuesto admite mano de obra, repuestos y aprobación total, parcial o rechazo. La reparación incluye reservas, retiros, avances y daños adicionales con aprobación. La calidad aprobada habilita liquidación; la entrega requiere saldo cubierto, receptor y firma. Un cambio de consumos posterior al control exige revisar calidad nuevamente. El rechazo del presupuesto permite liquidar solo el diagnóstico.

Las órdenes históricas conservan sus datos y su compatibilidad de estados. Todo diagnóstico nuevo, incluso sobre una orden histórica, debe vincularse a una recepción completa de esa orden; los diagnósticos históricos existentes no se alteran. Para ver cambios realizados desde otra sesión, actualizar la página.

## Acceso

El administrador gestiona asignaciones, cobros y catálogo de herramientas. El mecánico trabaja sobre órdenes asignadas y consulta herramientas. El cliente consulta sus órdenes y responde presupuestos y daños adicionales. Recepción y movimientos de inventario respetan los permisos específicos del servidor. Ver también `PERMISOS_SERVIDOR.md`.

## Inventario

Los movimientos se registran en un punto común con bloqueo de producto y actualización condicionada de existencias. Reservar aparta disponibilidad; retirar consume. Facturar y cobrar una pieza consumida concilian el consumo existente y descuentan solo la diferencia pendiente. Los reintentos con la misma clave no duplican operaciones; reutilizar la clave con otros datos produce conflicto. No se permite eliminar productos con historial.

Las entradas de devolución vinculadas a una orden validan el consumo neto y requieren administración. Anular una factura de un trabajo no devuelve automáticamente piezas instaladas. Los ajustes del catálogo dejan un movimiento auditable.

El escaneo admite cámara del teléfono en navegadores compatibles, lectores que escriben como teclado y entrada manual. Primero busca código de barras o código propio, y usa código de proveedor/distribuidor como alternativa. Los códigos ambiguos se rechazan. La lectura con el teléfono real del taller sigue pendiente de aceptación.

## Herramientas

Campos: código, nombre, marca, serie, ubicación, fecha de adquisición, observaciones y estado (disponible, mantenimiento o fuera de servicio). Este alcance no incluye préstamos ni asignaciones de herramientas.

## Datos existentes y puesta en marcha

El inicio crea las tablas nuevas y añade columnas compatibles para identificar el flujo y el origen del diagnóstico. La conciliación inicial incorpora evidencia de consumos históricos sin modificar las existencias físicas. Los posibles descuentos duplicados anteriores requieren conciliación con un conteo físico; no se corrigen inventando stock. Los códigos de barras duplicados preexistentes se notifican y requieren depuración antes de aplicar la unicidad.

La validación se hizo con bases aisladas, sin modificar datos de producción. Antes de actualizar un servidor existente, realizar respaldo y verificar migración sobre una copia. El almacenamiento de evidencias mantiene su acceso público actual; este cambio no implementa archivos privados.

## Validación anterior (antecedente)

- Backend: 83 pruebas aprobadas, incluidos flujo completo, permisos, idempotencia, reservas, devoluciones y herramientas.
- Frontend: comprobación TypeScript, cinco pruebas de estados/pagos y compilación de producción aprobadas.
- Navegador Chromium: recepción con cuatro archivos y firma, diagnóstico, presupuesto, aprobación de cliente a 360 px sin desbordamiento horizontal, retiro y reparación con mecánico, calidad, pago, entrega firmada, alta/edición de herramientas y entrada por código.
- Existencias verificadas al final del recorrido: 10 iniciales - 1 consumido + 2 recibidos = 11; sin errores JavaScript detectados.
- Diferencias de Git sin errores de espacios. La compilación advierte sobre tamaño de paquetes; la suite backend conserva un aviso de deprecación de la dependencia de pruebas.

Estas comprobaciones cubren los tres bloques implementados; no certifican todas las funcionalidades del proyecto ni sustituyen las pruebas de aceptación con el personal del taller.


## Revisión del Excel del 20 de noviembre de 2026

El recorrido de ingreso exige cliente y vehículo asociados, recepción con cuatro fotos (frente, posterior, lateral izquierdo y lateral derecho) y firma, y un diagnóstico escrito del mecánico. Se pueden guardar borradores de recepción, pero no diagnosticar hasta completarlos. El diagnóstico identifica orden, recepción, responsable activo, fecha y origen (criterio técnico, escáner o ambos). Cuando se usa escáner se requieren códigos o resultados escritos; una lectura sin códigos se puede describir sin inventarlos. El kilometraje del diagnóstico no puede ser menor al de recepción. Una orden finalizada o entregada no admite nuevos diagnósticos y la recepción queda protegida una vez iniciado el trabajo.

La pantalla `/diagnostico` permite elegir la orden del vehículo y abrir su recepción. `/ordenes/:id` ofrece campos de texto para los hallazgos y la interpretación del escáner, además de la revisión de los ocho sistemas del automóvil.

Las pruebas usan SQLite temporal y sustituyen el envío de correo. En un entorno normal ejecutar `.venv/bin/python -m pytest -q`. Si el entorno impide el socket local de aviso de asyncio, ejecutar `.venv/bin/python scripts/run_tests.py --sandbox-polling -q`; este modo únicamente limita la espera del selector y mantiene las solicitudes ASGI y la lógica real de la aplicación.

Los resultados de esta revisión se guardan en `informes/resultados_backend.txt` y `informes/resultados_backend.xml`. El archivo `informes/validacion_requisitos_openmotors.xlsx` contrasta los 66 RF y 24 RNF y distingue pruebas de API, cobertura parcial, funciones pendientes y comprobaciones que requieren el entorno real. Esta revisión no repitió la prueba de Chromium mencionada en el antecedente ni certifica navegadores, PostgreSQL, Supabase, correo, cámara, escáner físico o respaldos.

Resultado final de esta revisión: **121 pruebas backend aprobadas, sin fallos ni omisiones** (38 casos nuevos respecto de los 83 anteriores). Frontend: `npm test`, `npm run typecheck`, `npm run lint` y `npm run build` aprobados. Lint mantiene 12 advertencias y la compilación avisa sobre tamaño de paquetes y datos de Browserslist; el backend mantiene una advertencia de deprecación de Starlette/TestClient.


## Códigos de barras con el teléfono

En Inventario, crear o editar un producto ofrece **Leer etiqueta con teléfono** junto a Código de barras. La lectura rellena el código como texto (conserva ceros iniciales y letras); el usuario revisa los datos y guarda el producto para asociarlo a esa etiqueta. No es necesario generar una etiqueta nueva si el producto ya trae una. El mismo código no se puede asociar a dos productos.

En **Escaneo y movimientos**, pulsar **Escanear con teléfono**, autorizar la cámara y apuntar a una sola etiqueta. Al detectar un código se apaga la cámara y se consulta el producto. Después se elige entrada, salida para orden o devolución, se indica cantidad y motivo, y se pulsa **Confirmar movimiento**. Buscar o leer repetidamente no modifica existencias. Si el código es desconocido, un usuario autorizado puede abrir el alta del producto con la etiqueta ya rellenada.

La cámara utiliza la detección nativa disponible en el navegador (`BarcodeDetector`) y solicita preferentemente la cámara trasera, sin audio. Solicita únicamente los formatos de barras que admita el teléfono (EAN-13/EAN-8, UPC-A/UPC-E, Code 128/39/93, ITF y Codabar). Requiere HTTPS o localhost y permiso de cámara. La API tiene disponibilidad limitada: usar como primera opción Chrome actualizado en Android, comprobar el equipo real y mantener entrada manual para dispositivos no compatibles. No se certifica Safari/iPhone con esta implementación. Referencia de compatibilidad: https://developer.mozilla.org/en-US/docs/Web/API/BarcodeDetector

Cerrar el lector, navegar fuera de la pantalla o pasar la aplicación a segundo plano detiene la cámara. La captura tardía tras cancelar también se libera. Los permisos denegados, cámara ocupada y navegador no compatible muestran mensajes de recuperación. El lector no instala servicios ni envía video a servidores.

La nueva batería incluye 12 casos de control del lector con cámara/detector simulados y pruebas de identificación repetida por API sin movimientos ni pérdida de ceros iniciales. TypeScript, lint y compilación se revisan junto al cambio. La lectura óptica real queda pendiente: este entorno no dispone de cámara y restringe el arranque de Chromium. Los resultados específicos quedan en `informes/resultados_codigo_barras_*`.

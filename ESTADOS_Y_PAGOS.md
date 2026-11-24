# Estados de órdenes y pagos

Trabajo: 0 pendiente, 1 en proceso, 2 finalizada, 3 entregada.
Transiciones: 0→1→2→3. Se permite 2→1 para reproceso antes de entregar.
Repetir un estado no cambia sus fechas. Cobrar no cambia el trabajo.
Las órdenes nuevas empiezan pendientes. La entrega con costo exige pago completo.

Pago: PENDIENTE, PARCIAL, PAGADO. Los abonos guardan monto, método, fecha y autor
obtenido de la sesión. POST /api/registros/{id}/pagos acepta monto_recibido,
metodo_pago, numero_referencia e id_operacion (clave de reintento).
El saldo y el total cobrado se devuelven con cada orden. Los informes de ingresos
usan movimientos por fecha de pago; los saldos históricos sin movimientos usan
la fecha conservada y no constituyen una reconstrucción de su historial.

La migración se ejecuta al iniciar el backend y es idempotente. No se ha aplicado
a una base de producción como parte del desarrollo. Antes de desplegar, respaldar
la base y probar la migración con una copia. estado_legacy conserva el código
original y revision_estado identifica valores ambiguos que deben revisarse.
No se deduce pago de una factura: solo de la antigua marca 7 o una nota pagada.
Una orden antigua 4 se representa como entregada pero queda marcada para revisión;
los estados 2/3 se interpretan de forma conservadora según las fechas disponibles.
Las decisiones de presupuestos continúan en el presupuesto y no agregan estados
de trabajo. El rechazo no significa automáticamente entrega ni pago.

No se incluye en este bloque el rediseño de permisos de todos los módulos,
reembolsos, devoluciones ni la unificación completa de consumos de inventario.

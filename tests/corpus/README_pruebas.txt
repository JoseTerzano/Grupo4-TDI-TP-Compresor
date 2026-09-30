CORPUS DE PRUEBAS - TEORIA DE LA INFORMACION
=============================================

Objetivo
--------
Estos cuatro archivos forman un corpus comun para comparar compresores propios
y soluciones externas bajo las mismas condiciones.

Archivos
--------
1) prueba_1_pequena.txt
   Archivo muy pequeno para mostrar paso a paso el funcionamiento del algoritmo.

2) prueba_2_texto_natural.txt
   Texto natural original en espanol. Tamano objetivo: 100 KiB.

3) prueba_3_alta_repeticion.txt
   Texto con rachas largas y bloques repetidos. Tamano objetivo: 100 KiB.

4) prueba_4_baja_repeticion.txt
   Texto ASCII pseudoaleatorio con distribucion aproximadamente uniforme sobre
   caracteres imprimibles. Tamano objetivo: 100 KiB. Semilla fija: 2026.

IMPORTANTE
----------
- Los archivos 2, 3 y 4 tienen exactamente el mismo tamano para facilitar la comparacion.
- La integridad debe comprobarse byte a byte.
- Puede utilizarse SHA-256 para validar que el archivo reconstruido sea identico.
- Todos los grupos deben usar exactamente estos archivos sin modificarlos.

Tamanos y SHA-256
-----------------
prueba_1_pequena.txt
  bytes: 64
  sha256: 8a0d7e04cc6347ca94cf03f7329ad7bf5881bfaff6d26da42e86166822c20051

prueba_2_texto_natural.txt
  bytes: 102400
  sha256: 410d0deaf3cdfd3a51595d084445727ccc1c2c154b910738e0e32934bbbae403

prueba_3_alta_repeticion.txt
  bytes: 102400
  sha256: a54f4a85a8695e1bec7cf49603301d97bd08c89f98dddb09fb0605fa1f88e36e

prueba_4_baja_repeticion.txt
  bytes: 102400
  sha256: 7b7b0ac6050531d99b338e2db14c188565bbf12f4b08a97b4398b7eda28b6d61


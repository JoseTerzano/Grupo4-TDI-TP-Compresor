# Compresor TDI — Huffman dinámico (FGK) vs Brotli q5 vs gzip -6

Práctico de Máquina 2 — Teoría de la Información (UNSJ, 2026).
Desafío de Proveedores de Compresión.

## 1. El proveedor y sus dos soluciones

| Rol | Solución | Configuración |
|---|---|---|
| **Autoría propia** (Sorteo A n.º 4) | Huffman dinámico **FGK** (Faller–Gallager–Knuth) en Python puro | formato `.tdi`, cabecera fija de 20 B |
| **Tercerizada** (Sorteo B n.º 9) | **Brotli** | CLI oficial `brotli 1.1.0`, `-q 5`, ventana por defecto (lgwin 22) |
| **Baseline cátedra** | **gzip** | `gzip -n -6` (sin nombre ni timestamp), gzip 1.13 |

El núcleo propio no usa ninguna librería de compresión (`zlib`, `gzip`, `bz2`,
`lzma`, `brotli`… prohibidas). Solo stdlib: `struct`, `binascii` (CRC32),
`hashlib`, `argparse`, `time`.

## 2. Algoritmo: Huffman dinámico FGK

### Idea
Huffman estático necesita dos pasadas (contar frecuencias, luego codificar) y
**guardar el árbol o la tabla** en el archivo. El Huffman **dinámico** hace una
sola pasada: codificador y decodificador arrancan con el **mismo árbol inicial**
(un único nodo *NYT*, "Not Yet Transmitted") y lo **actualizan en espejo**
después de cada símbolo. Como ambos ven exactamente la misma secuencia de
símbolos, sus árboles son idénticos en todo momento → **no se transmite el
árbol ni las frecuencias**. Solo hace falta saber cuántos bytes reconstruir.

### Propiedad de hermanos
Un árbol binario con pesos es de Huffman si y solo si sus nodos pueden numerarse
de modo que:
1. los pesos sean **no decrecientes** al recorrer los nodos por número, y
2. cada par de hermanos sea consecutivo y cada nodo tenga número menor que su padre.

### Codificación de un símbolo
- **Símbolo nuevo**: se emite el código del **NYT** + el byte crudo (8 bits).
  El NYT se divide en *(nuevo NYT, hoja del símbolo)*.
- **Símbolo conocido**: se emite su código (camino raíz→hoja; 0 = izquierda, 1 = derecha).
- **Fin de datos**: no hay símbolo EOF; el decodificador se detiene al producir
  `tamaño_original` bytes (viene en la cabecera).

### Actualización (FGK)
Desde la hoja hasta la raíz, en cada nodo *n*:
1. buscar el **líder del bloque**: el nodo de **mayor número con el mismo peso** que *n*;
2. si el líder no es *n* ni su padre, **intercambiar** los subárboles de *n* y del líder;
3. incrementar el peso y pasar al padre.

El intercambio garantiza que, tras incrementar, los pesos sigan ordenados → el
árbol sigue siendo de Huffman para las frecuencias vistas hasta el momento.

### Implementación ([tdi/adaptive_huffman.py](tdi/adaptive_huffman.py))
- Arrays paralelos `weight`, `parent`, `left`, `symbol` indexados por **número
  de nodo** + `leaf_of[256]`. Raíz = 512.
- El NYT en la posición *k* se divide en NYT = *k−2* (izq.) y hoja = *k−1* (der.).
  Los hermanos ocupan siempre pares (par, impar), así que **el bit que aporta un
  nodo a su código es `n & 1`** y el hijo por bit *b* es `left[n] + b`.
- Intercambio = intercambiar el *contenido* de dos posiciones (subárbol) y
  corregir `parent` de los hijos / `leaf_of` de las hojas: **O(1)**.
- Líder: **escaneo hacia arriba** mientras `weight[m+1] == w` (centinela en 513).
  Costo O(tamaño del bloque). Se prefirió a un dict `leader[peso]` porque en FGK
  el orden se rompe transitoriamente (la hoja hermana del NYT se incrementa antes
  que su padre), lo que complica mantener el dict; en la práctica los bloques son
  chicos y el escaneo es más rápido en CPython.
- Código de un símbolo: subir hoja→raíz acumulando bits en un `int` (orden inverso).
- Bits: [tdi/bitio.py](tdi/bitio.py) acumula en un `int` y vuelca bytes a un
  `bytearray`; nunca se concatenan strings `'0'/'1'`.
- Espacio: 256 bytes + NYT = 257 hojas → **513** nodos (0..512). Se conserva el
  NYT aunque ya hayan aparecido los 256 bytes (costo: una hoja de peso 0).
- Invariante verificable: `AdaptiveHuffmanTree(check=True)` comprueba la
  propiedad de hermanos después de cada update (solo en tests, no en producción).

## 3. Traza real de `prueba_1_pequena.txt`

Generada con `python compressor.py tests/corpus/prueba_1_pequena.txt results/prueba_1.tdi --trace`
(completa en [results/traza_prueba_1.txt](results/traza_prueba_1.txt)).
Formato del árbol: `número:peso:símbolo`, raíz primero; `·` = nodo interno.

```
#0       'A'  NUEVO (NYT+8b)  bits=01000001               ( 8 b, acum 8)
       árbol: 512:1:·  511:1:'A'  510:0:NYT
#1       'B'  NUEVO (NYT+8b)  bits=001000010              ( 9 b, acum 17)
       árbol: 512:2:·  511:1:'A'  510:1:·  509:1:'B'  508:0:NYT
#2       'R'  NUEVO (NYT+8b)  bits=0001010010             (10 b, acum 27)
       árbol: 512:3:·  511:2:·  510:1:'A'  509:1:'B'  508:1:·  507:1:'R'  506:0:NYT
#3       'A'  conocido        bits=0                      ( 1 b, acum 28)
       árbol: 512:4:·  511:2:·  510:2:'A'  509:1:'B'  508:1:·  507:1:'R'  506:0:NYT
#4       'C'  NUEVO (NYT+8b)  bits=10001000011            (11 b, acum 39)
       árbol: 512:5:·  511:3:·  510:2:'A'  509:2:·  508:1:'B'  507:1:'R'  506:1:·  505:1:'C'  504:0:NYT
#5       'A'  conocido        bits=0                      ( 1 b, acum 40)
       árbol: 512:6:·  511:3:·  510:3:'A'  509:2:·  508:1:'B'  507:1:'R'  506:1:·  505:1:'C'  504:0:NYT
#6       'D'  NUEVO (NYT+8b)  bits=110001000100           (12 b, acum 52)
       árbol: 512:7:·  511:4:·  510:3:'A'  509:2:·  508:2:·  507:1:'R'  506:1:'B'  505:1:'C'  504:1:·  503:1:'D'  502:0:NYT
#7       'A'  conocido        bits=0                      ( 1 b, acum 53)
       árbol: 512:8:·  511:4:·  510:4:'A'  509:2:·  508:2:·  507:1:'R'  506:1:'B'  505:1:'C'  504:1:·  503:1:'D'  502:0:NYT
#8       'B'  conocido        bits=110                    ( 3 b, acum 56)
       árbol: 512:9:·  511:5:·  510:4:'A'  509:3:·  508:2:·  507:2:'B'  506:1:'R'  505:1:'C'  504:1:·  503:1:'D'  502:0:NYT
#9       'R'  conocido        bits=110                    ( 3 b, acum 59)
       árbol: 512:10:·  511:6:·  510:4:'A'  509:4:·  508:2:·  507:2:'B'  506:2:'R'  505:1:'C'  504:1:·  503:1:'D'  502:0:NYT
```

Lectura:
- `#0`: el árbol es solo NYT (código vacío) → se emiten únicamente los 8 bits de `'A'` (0x41).
- `#1`: NYT = `0` (hijo izquierdo de la raíz) + `01000010` (`'B'`).
- `#4`: NYT está en 506 → camino 511(1)·508(0)·506(0) = `100`, + `01000011` (`'C'`).
- `#3, #5, #7`: `'A'` es la hoja más pesada, hija directa de la raíz → 1 bit.
- `#8`: `'B'` estaba en 506 con peso 1 dentro del bloque {507,506,505,504,503}; el
  líder era 507 (`'R'`) → se intercambian y `'B'` sube; lo mismo ocurre en cada ancestro.

Resultado: 64 B → 331 bits de payload (42 B, 5,17 bits/símbolo) + 20 B de cabecera = **62 B**.
El decodificador (`decompressor.py … --trace`) imprime exactamente la misma traza.

## 4. Formato `.tdi` byte a byte

Little-endian, `struct.Struct("<4sBBBQIB")` ([tdi/format.py](tdi/format.py)):

| Offset | Tamaño | Campo | Valor |
|---:|---:|---|---|
| 0 | 4 B | magic | `b"TDI1"` |
| 4 | 1 B | versión | `1` |
| 5 | 1 B | id algoritmo | `1` = FGK (`2` = Vitter, reservado/no implementado) |
| 6 | 1 B | flags | `0` (reservado; ≠ 0 se rechaza) |
| 7 | 8 B | tamaño original | `uint64` |
| 15 | 4 B | CRC32 del original | `binascii.crc32` |
| 19 | 1 B | bits válidos del último byte | 1–8 (0 si payload vacío) |
| 20 | resto | payload | bitstream MSB-first, relleno con ceros |

**Cabecera fija = 20 B. No se almacena modelo, árbol ni tabla**: es la ventaja
clave del método adaptativo. Overhead O = 20/Sc·100.

Ejemplo real (`results/prueba_1.tdi`):
```
54 44 49 31 | 01 | 01 | 00 | 40 00 00 00 00 00 00 00 | f5 d6 cb 1e | 03 | 41 21 0a 48 ...
  "TDI1"     ver  FGK  flags   So = 64                  CRC 0x1ecbd6f5  331 mod 8 = 3
```

Validaciones del descompresor (excepción propia, mensaje claro, **sin traceback**):

| Situación | Excepción | Exit code |
|---|---|---:|
| archivo inexistente / ilegible | `InputFileError` | 2 |
| magic inválido | `InvalidMagicError` | 3 |
| versión o flags no soportados | `UnsupportedVersionError` | 3 |
| algoritmo no soportado | `UnsupportedAlgorithmError` | 3 |
| cabecera truncada (< 20 B) | `TruncatedHeaderError` | 3 |
| bitstream agotado antes de `tamaño_original` bytes | `BitstreamExhaustedError` | 4 |
| bits sobrantes, relleno ≠ 0, "símbolo nuevo" ya existente, `bits_último_byte` fuera de rango | `CorruptDataError` | 4 |
| CRC32 no coincide | `ChecksumError` | 5 |
| `--verify`: SHA-256 difiere | — (`INTEGRIDAD FAIL`) | 6 |

## 5. Uso

Requisitos: **Python ≥ 3.10**, sin dependencias de Python para la solución propia.
Para el benchmark: `brotli` y `gzip` en el PATH.

```bash
python compressor.py tests/corpus/prueba_2_texto_natural.txt salida.tdi
```
```bash
python decompressor.py salida.tdi reconstruido.txt --verify tests/corpus/prueba_2_texto_natural.txt
```
```bash
python compressor.py tests/corpus/prueba_1_pequena.txt p1.tdi --trace
```
```bash
python -m unittest discover -s tests -v
```
```bash
python benchmark.py --reps 5
```

Salida del compresor: entrada, salida, So, Sc, ratio, ahorro %, tamaño relativo,
cabecera y overhead, tiempo del núcleo y total, throughput, algoritmo, símbolos
distintos, altura final del árbol, bits de payload, bits/símbolo y SHA-256.
El descompresor agrega CRC32, SHA-256 reconstruido y, con `--verify`, SHA-256
del original + `INTEGRIDAD OK/FAIL`.

### Instalar Brotli / gzip
- Debian/Ubuntu: `sudo apt install brotli gzip`
- macOS: `brew install brotli`
- Windows: `choco install brotli` o MSYS2 `pacman -S mingw-w64-x86_64-brotli`;
  gzip viene con Git for Windows.
- Fallback (documentado en la tabla si se usa): `pip install brotli` — el
  benchmark lo usa automáticamente con `quality=5` si no encuentra el CLI.

### Estructura
```
compressor.py / decompressor.py   CLIs
tdi/bitio.py                      BitWriter / BitReader
tdi/format.py                     cabecera, constantes, validaciones, excepciones
tdi/adaptive_huffman.py           AdaptiveHuffmanTree (FGK) + encode / decode
tdi/codec.py                      contenedor completo (cabecera + payload + CRC)
tdi/trace.py                      modo --trace
benchmark.py                      propio vs Brotli q5 vs gzip -6
tests/                            corpus + test_roundtrip.py + test_errors.py
results/                          results.csv, results.json, tabla.md, entorno.txt, traza
```

## 6. Resultados (medidos, no estimados)

Entorno ([results/entorno.txt](results/entorno.txt)): AMD Ryzen 7 7735HS, Windows 11
(10.0.26200), CPython 3.13.14, brotli 1.1.0, gzip 1.13. Mediana de 5
repeticiones, 1 warm-up descartado. **Todos los tiempos son por subprocess**
(las tres soluciones pagan el arranque de su proceso). SHA-256 del round-trip
verificado en cada repetición. Tabla completa: [results/tabla.md](results/tabla.md).

| Archivo | Solución | So | Sc | Ratio | Ahorro% | Tc_ms | Td_ms | Vc MB/s | Vd MB/s | Overhead% | Weissman | SHA | Cota orden‑0 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| prueba_1 | Propia FGK | 64 | 62 | 1,032 | 3,12 | 169,17 | 172,48 | 0,000 | 0,000 | 32,258 | 0,623* | OK | 2,416 |
| prueba_1 | Brotli q5 | 64 | 48 | 1,333 | 25,00 | 16,18 | 16,45 | 0,004 | 0,004 | n/d | 1,483* | OK | 2,416 |
| prueba_1 | gzip -6 | 64 | 59 | 1,085 | 7,81 | 28,74 | 29,42 | 0,002 | 0,002 | 30,508 | 1,000* | OK | 2,416 |
| prueba_2 | Propia FGK | 102400 | 54529 | 1,878 | 46,75 | 409,78 | 494,34 | 0,250 | 0,207 | 0,037 | 0,020 | OK | 1,891 |
| prueba_2 | Brotli q5 | 102400 | 1143 | 89,589 | 98,88 | 17,27 | 28,31 | 5,931 | 3,617 | n/d | 1,970 | OK | 1,891 |
| prueba_2 | gzip -6 | 102400 | 1919 | 53,361 | 98,13 | 28,28 | 29,63 | 3,621 | 3,456 | 0,938 | 1,000 | OK | 1,891 |
| prueba_3 | Propia FGK | 102400 | 36661 | 2,793 | 64,20 | 354,67 | 408,69 | 0,289 | 0,251 | 0,055 | 0,013 | OK | 2,894 |
| prueba_3 | Brotli q5 | 102400 | 64 | 1600,000 | 99,94 | 17,91 | 37,96 | 5,716 | 2,698 | n/d | 15,337 | OK | 2,894 |
| prueba_3 | gzip -6 | 102400 | 914 | 112,035 | 99,11 | 22,17 | 22,73 | 4,618 | 4,505 | 1,969 | 1,000 | OK | 2,894 |
| prueba_4 | Propia FGK | 102400 | 85409 | 1,199 | 16,59 | 558,30 | 644,52 | 0,183 | 0,159 | 0,023 | 0,542 | OK | 1,218 |
| prueba_4 | Brotli q5 | 102400 | 85044 | 1,204 | 16,95 | 26,52 | 26,52 | 3,862 | 3,861 | n/d | 1,050 | OK | 1,218 |
| prueba_4 | gzip -6 | 102400 | 85207 | 1,202 | 16,79 | 31,05 | 36,77 | 3,298 | 2,785 | 0,021 | 1,000 | OK | 1,218 |

\* Prueba 1 fuera del ranking temporal (indicación de la cátedra); Weissman solo ilustrativo.

**Weissman global** (pruebas 2–4, ref = gzip -n -6, T en ms, α = 1):

| Solución | ΣSo | ΣSc | Rglobal | Tglobal (ms) | Wglobal |
|---|---:|---:|---:|---:|---:|
| Propia FGK | 307200 | 176599 | 1,740 | 1313,79 | **0,305** |
| Brotli q5 | 307200 | 86251 | 3,562 | 60,34 | **1,095** |
| gzip -6 | 307200 | 88040 | 3,489 | 81,27 | 1,000 |

**Núcleo propio en proceso** (sin arranque de Python ni E/S):

| Archivo | Tc (ms) | Td (ms) | Vc (MB/s) | Vd (MB/s) | Símb. distintos | Altura árbol | bits/símbolo | H₀ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| prueba_1 | 0,21 | 0,22 | 0,31 | 0,30 | 14 | 7 | 5,172 | 3,311 |
| prueba_2 | 277,82 | 298,31 | 0,37 | 0,34 | 51 | 15 | 4,259 | 4,230 |
| prueba_3 | 195,74 | 224,97 | 0,52 | 0,46 | 11 | 7 | 2,863 | 2,764 |
| prueba_4 | 412,87 | 510,95 | 0,25 | 0,20 | 95 | 8 | 6,671 | 6,569 |

(Los tiempos varían ±10–20 % entre corridas; re-ejecutar `benchmark.py` regenera todo.)

## 7. Análisis

**Huffman dinámico es un modelo de orden 0.** Solo explota la frecuencia de
cada byte, no repeticiones de cadenas ni contexto. Su techo teórico es la cota
orden‑0 = 8/H₀. En todos los archivos queda **levemente por debajo** de esa
cota (1,878 vs 1,891; 2,793 vs 2,894; 1,199 vs 1,218), como debe ser: pagamos
el costo de aprendizaje (cada símbolo nuevo = código NYT + 8 bits), la hoja NYT
que ocupa espacio de código y el redondeo a longitudes enteras de bits.
En prueba_3 la brecha es mayor (0,10 bit/símbolo) porque la distribución es
muy sesgada y Huffman no puede asignar menos de 1 bit al símbolo dominante.

**prueba_2 (texto natural) y prueba_3 (alta repetición):** FGK logra ~1,9 y ~2,8
contra 53–112 de gzip y 90–1600 de Brotli. No es un defecto de la
implementación: gzip (Deflate) y Brotli usan **LZ77 + Huffman** y reemplazan
secciones enteras repetidas por referencias (distancia, longitud). Brotli además
tiene diccionario estático, modelado de contexto y ventana de 4 MiB, por eso en
prueba_3 comprime 100 KiB a 64 B. Ningún código de orden 0 puede ver esas
repeticiones.

**prueba_4 (≈ uniforme sobre 95 imprimibles):** sin repeticiones útiles, todos
convergen a ≈1,2 ≈ 8/log₂95. Aquí FGK compite de igual a igual en ratio
(85 409 B vs 85 207 gzip vs 85 044 Brotli, diferencias < 0,5 %). Aclaración
crítica: la cabecera mínima **no** alcanza para ganar: el costo de aprendizaje
del modelo adaptativo (~95 símbolos × 8 bits crudos + códigos NYT) y la hoja NYT
pesan más que los 18 B de gzip. gzip/Brotli construyen Huffman óptimo por
bloque con las frecuencias reales.

**prueba_1 (64 B):** domina el overhead. La cabecera `.tdi` es el 32 % del
archivo; los 14 símbolos distintos cuestan 14 × 8 bits crudos = 112 de los 331
bits del payload. gzip paga 18 B de contenedor; Brotli no tiene contenedor y
gana (48 B).

**Weissman:** global 0,305 para FGK (< 1 → gzip es mejor compromiso). Menos
extremo de lo que sugieren los ratios porque el logaritmo aplasta la diferencia
de tiempo (ln 1314 / ln 81 ≈ 1,63). Causas: (1) modelo de orden 0 → Rglobal
1,74 vs 3,49; (2) Python puro vs C → ~16× más lento; además ~95 ms de cada
medición son solo el arranque del intérprete de Python. Es consecuencia del
modelo y del lenguaje, no un error. Brotli q5 supera a gzip (1,095): más ratio
y más rápido.

**Ventajas reales del método:** una sola pasada, sin tabla ni árbol en el
archivo (cabecera fija de 20 B), apto para streaming, simétrico y simple de
verificar (el decodificador reproduce la misma traza).

## 8. Tests

`python -m unittest discover -s tests -v` (29 tests, ~13 s):
- **Round-trip** de los 4 archivos del corpus (bytes + SHA-256), verificación de
  que el corpus coincide con `README_pruebas.txt`, y que el payload nunca baja
  de n·H₀.
- **Casos borde**: vacío (solo cabecera, 20 B), 1 byte (21 B), un símbolo × 10 000,
  los 256 bytes, `os.urandom(100_000)` (se expande < 1 % y se reconstruye),
  alfabetos aleatorios con 8 semillas, CRLF y bytes no UTF-8.
- **Invariante**: propiedad de hermanos verificada tras **cada** update
  (modo `check=True`, solo en tests).
- **Errores**: magic, versión, flags, algoritmo, cabecera truncada, payload
  truncado, tamaño declarado mayor, bytes sobrantes, bytes del payload alterados
  (cientos de posiciones × 3 máscaras: todos detectados por CRC o bitstream),
  CRC alterado, archivo inexistente por CLI (exit ≠ 0, sin traceback),
  `--verify` contra archivo distinto (exit 6).

## 9. Limitaciones conocidas

- **Vitter (algoritmo Λ) no implementado**: id 2 reservado en la cabecera; hoy se
  rechaza con "algoritmo no soportado". Mejora esperada: leve (árbol de menor altura).
- **Velocidad**: ~0,2–0,5 MB/s (CPython puro). 100 KiB ≈ 0,2–0,5 s; archivos de
  varios MB tardarían segundos a decenas de segundos. El arranque de Python
  (~95 ms) domina en archivos chicos.
- **Todo en memoria**: lee el archivo completo; no procesa streams de tamaño arbitrario
  aunque el algoritmo lo permitiría.
- **Orden 0**: no puede aprovechar repeticiones ni contexto (ver análisis).
- **CRC32** detecta corrupción accidental, no manipulación maliciosa.
- Tiempos medidos en una sola máquina Windows; Weissman es sensible a plataforma y unidad.

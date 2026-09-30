# Resultados del benchmark

Entorno: AMD Ryzen 7 7735HS with Radeon Graphics · Windows 11 (10.0.26200) · CPython 3.13.14. Mediana de 5 repeticiones (1 warm-up descartado). Tiempos por subprocess (incluyen arranque de proceso).

| Archivo | Solución | So | Sc | Ratio | Ahorro% | Tc_ms | Td_ms | Vc (MB/s) | Vd (MB/s) | Overhead% | Weissman | SHA_OK | Cota orden-0 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| prueba_1_pequena | Propia: Huffman dinámico FGK | 64 | 62 | 1.032 | 3.12 | 169.17 | 172.48 | 0.000 | 0.000 | 32.258 | 0.623 | OK | 2.416 |
| prueba_1_pequena | Externa: Brotli q5 | 64 | 48 | 1.333 | 25.00 | 16.18 | 16.45 | 0.004 | 0.004 | n/d | 1.483 | OK | 2.416 |
| prueba_1_pequena | Baseline: gzip -n -6 | 64 | 59 | 1.085 | 7.81 | 28.74 | 29.42 | 0.002 | 0.002 | 30.508 | 1.000 | OK | 2.416 |
| prueba_2_texto_natural | Propia: Huffman dinámico FGK | 102400 | 54529 | 1.878 | 46.75 | 409.78 | 494.34 | 0.250 | 0.207 | 0.037 | 0.020 | OK | 1.891 |
| prueba_2_texto_natural | Externa: Brotli q5 | 102400 | 1143 | 89.589 | 98.88 | 17.27 | 28.31 | 5.931 | 3.617 | n/d | 1.970 | OK | 1.891 |
| prueba_2_texto_natural | Baseline: gzip -n -6 | 102400 | 1919 | 53.361 | 98.13 | 28.28 | 29.63 | 3.621 | 3.456 | 0.938 | 1.000 | OK | 1.891 |
| prueba_3_alta_repeticion | Propia: Huffman dinámico FGK | 102400 | 36661 | 2.793 | 64.20 | 354.67 | 408.69 | 0.289 | 0.251 | 0.055 | 0.013 | OK | 2.894 |
| prueba_3_alta_repeticion | Externa: Brotli q5 | 102400 | 64 | 1600.000 | 99.94 | 17.91 | 37.96 | 5.716 | 2.698 | n/d | 15.337 | OK | 2.894 |
| prueba_3_alta_repeticion | Baseline: gzip -n -6 | 102400 | 914 | 112.035 | 99.11 | 22.17 | 22.73 | 4.618 | 4.505 | 1.969 | 1.000 | OK | 2.894 |
| prueba_4_baja_repeticion | Propia: Huffman dinámico FGK | 102400 | 85409 | 1.199 | 16.59 | 558.30 | 644.52 | 0.183 | 0.159 | 0.023 | 0.542 | OK | 1.218 |
| prueba_4_baja_repeticion | Externa: Brotli q5 | 102400 | 85044 | 1.204 | 16.95 | 26.52 | 26.52 | 3.862 | 3.861 | n/d | 1.050 | OK | 1.218 |
| prueba_4_baja_repeticion | Baseline: gzip -n -6 | 102400 | 85207 | 1.202 | 16.79 | 31.05 | 36.77 | 3.298 | 2.785 | 0.021 | 1.000 | OK | 1.218 |

## Weissman global (pruebas 2–4, ref = gzip -n -6, T en ms)

| Solución | ΣSo | ΣSc | Rglobal | Tglobal_ms | Wglobal |
|---|---:|---:|---:|---:|---:|
| Propia: Huffman dinámico FGK | 307200 | 176599 | 1.740 | 1313.79 | 0.305 |
| Externa: Brotli q5 | 307200 | 86251 | 3.562 | 60.34 | 1.095 |
| Baseline: gzip -n -6 | 307200 | 88040 | 3.489 | 81.27 | 1.000 |

## Núcleo propio en proceso (sin arranque de Python ni E/S)

| Archivo | Tc núcleo (ms) | Td núcleo (ms) | Vc (MB/s) | Vd (MB/s) |
|---|---:|---:|---:|---:|
| prueba_1_pequena | 0.21 | 0.22 | 0.310 | 0.298 |
| prueba_2_texto_natural | 277.82 | 298.31 | 0.369 | 0.343 |
| prueba_3_alta_repeticion | 195.74 | 224.97 | 0.523 | 0.455 |
| prueba_4_baja_repeticion | 412.87 | 510.95 | 0.248 | 0.200 |

Notas:
- Prueba 1 se excluye del ranking temporal (lo indica la cátedra); su Weissman es solo ilustrativo.
- Weissman = (R/Rref)·(ln Tref/ln T), T = Tc en ms, α = 1; "no definido" si T ≤ 1 ms.
- Overhead: .tdi = 20 B de cabecera fija; gzip = 18 B (cabecera 10 B + trailer 8 B); Brotli no tiene cabecera de contenedor (n/d).
- Cota orden-0 = 8/H₀ (entropía empírica de bytes): máximo ratio alcanzable por cualquier código de orden 0 sin contar cabecera.

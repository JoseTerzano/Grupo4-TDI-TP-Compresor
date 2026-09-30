#!/usr/bin/env python3
"""Compresor .tdi — Huffman dinámico FGK.

Uso: python compressor.py entrada.txt salida.tdi [--trace] [--trace-limit N]
"""

from __future__ import annotations

import argparse
import sys
import time

from tdi import codec
from tdi.cli_common import (fail, print_rows, read_input, sha256, size_report,
                            throughput, write_output)
from tdi.format import ALGO_FGK, ALGO_NAMES, TDIError
from tdi.trace import make_tracer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compresor Huffman dinámico (FGK) -> .tdi")
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--trace", action="store_true",
                    help="imprime paso a paso cada símbolo y el árbol")
    ap.add_argument("--trace-limit", type=int, default=None,
                    help="máximo de símbolos a mostrar en la traza")
    ap.add_argument("--quiet", action="store_true", help="sin reporte")
    args = ap.parse_args(argv)

    t0 = time.perf_counter_ns()
    try:
        data = read_input(args.entrada)
        tracer = make_tracer(limit=args.trace_limit) if args.trace else None
        if tracer:
            print("== Traza de compresión (número:peso:símbolo, raíz primero) ==")
        tc0 = time.perf_counter_ns()
        res = codec.compress(data, trace=tracer)
        core_ns = time.perf_counter_ns() - tc0
        write_output(args.salida, res.blob)
    except TDIError as e:
        fail(str(e), e.exit_code)
    total_ns = time.perf_counter_ns() - t0

    if args.quiet:
        return 0
    so, sc, enc = len(data), len(res.blob), res.enc
    rows = [("Entrada", args.entrada), ("Salida", args.salida),
            ("Algoritmo", ALGO_NAMES[ALGO_FGK])]
    rows += size_report(so, sc)
    rows += [
        ("Tiempo núcleo (encode)", f"{core_ns / 1e6:.2f} ms"),
        ("Tiempo total (E/S incl.)", f"{total_ns / 1e6:.2f} ms"),
        ("Throughput núcleo", throughput(so, core_ns)),
        ("Símbolos distintos", str(enc.distinct)),
        ("Altura final del árbol", str(enc.height)),
        ("Bits de payload", str(enc.bit_length)),
        ("Bits/símbolo promedio", f"{enc.bit_length / so:.4f}" if so else "n/d"),
        ("SHA-256 original", sha256(data)),
    ]
    print_rows("Compresión", rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

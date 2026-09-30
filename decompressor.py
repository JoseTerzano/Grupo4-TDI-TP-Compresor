#!/usr/bin/env python3
"""Descompresor .tdi — Huffman dinámico FGK.

Uso: python decompressor.py salida.tdi reconstruido.txt [--verify original.txt] [--trace]
"""

from __future__ import annotations

import argparse
import sys
import time

from tdi import codec
from tdi.cli_common import (fail, print_rows, read_input, sha256, size_report,
                            throughput, write_output)
from tdi.format import ALGO_NAMES, TDIError
from tdi.trace import make_tracer

EXIT_VERIFY_FAIL = 6


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Descompresor .tdi (Huffman dinámico FGK)")
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("--verify", metavar="ORIGINAL",
                    help="compara SHA-256 del reconstruido contra este archivo")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--trace-limit", type=int, default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.perf_counter_ns()
    try:
        blob = read_input(args.entrada)
        tracer = make_tracer(limit=args.trace_limit) if args.trace else None
        if tracer:
            print("== Traza de descompresión (número:peso:símbolo, raíz primero) ==")
        td0 = time.perf_counter_ns()
        data, header = codec.decompress(blob, trace=tracer)
        core_ns = time.perf_counter_ns() - td0
        write_output(args.salida, data)
        original = read_input(args.verify) if args.verify else None
    except TDIError as e:
        fail(str(e), e.exit_code)
    total_ns = time.perf_counter_ns() - t0

    so, sc = len(data), len(blob)
    h_rec = sha256(data)
    ok = None
    if original is not None:
        h_orig = sha256(original)
        ok = h_orig == h_rec and original == data

    if not args.quiet:
        rows = [("Entrada", args.entrada), ("Salida", args.salida),
                ("Algoritmo", ALGO_NAMES[header.algo]),
                ("Versión formato", str(header.version))]
        rows += size_report(so, sc)
        rows += [
            ("Tiempo núcleo (decode)", f"{core_ns / 1e6:.2f} ms"),
            ("Tiempo total (E/S incl.)", f"{total_ns / 1e6:.2f} ms"),
            ("Throughput núcleo", throughput(so, core_ns)),
            ("CRC32", f"{header.crc32:08x} OK"),
            ("SHA-256 reconstruido", h_rec),
        ]
        if original is not None:
            rows.append(("SHA-256 original", h_orig))
            rows.append(("INTEGRIDAD", "OK" if ok else "FAIL"))
        print_rows("Descompresión", rows)
    if ok is False:
        print("ERROR: INTEGRIDAD FAIL: SHA-256 difiere del original", file=sys.stderr)
        return EXIT_VERIFY_FAIL
    return 0


if __name__ == "__main__":
    sys.exit(main())

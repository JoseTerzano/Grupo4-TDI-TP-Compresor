"""Utilidades compartidas por compressor.py y decompressor.py."""

from __future__ import annotations

import hashlib
import os
import sys

from .format import HEADER_SIZE, InputFileError

MB = 1_000_000  # throughput en MB/s con MB = 10^6 B


def read_input(path: str) -> bytes:
    if not os.path.exists(path):
        raise InputFileError(f"archivo inexistente: {path}")
    if not os.path.isfile(path):
        raise InputFileError(f"no es un archivo regular: {path}")
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        raise InputFileError(f"no se pudo leer {path}: {e.strerror}") from e


def write_output(path: str, data: bytes) -> None:
    try:
        with open(path, "wb") as f:
            f.write(data)
    except OSError as e:
        raise InputFileError(f"no se pudo escribir {path}: {e.strerror}") from e


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def throughput(nbytes: int, ns: int) -> str:
    if ns <= 0:
        return "n/d"
    return f"{nbytes / MB / (ns / 1e9):.3f} MB/s"


def size_report(so: int, sc: int) -> list[tuple[str, str]]:
    rows = [("Tamaño original (So)", f"{so} B"),
            ("Tamaño comprimido (Sc)", f"{sc} B")]
    if sc:
        rows.append(("Ratio R = So/Sc", f"{so / sc:.4f}"))
    if so:
        rows.append(("Ahorro (1-Sc/So)·100", f"{(1 - sc / so) * 100:.2f} %"))
        rows.append(("Tamaño relativo", f"{sc / so * 100:.2f} %"))
    rows.append(("Cabecera", f"{HEADER_SIZE} B"))
    if sc:
        rows.append(("Overhead 20/Sc·100", f"{HEADER_SIZE / sc * 100:.3f} %"))
    return rows


def print_rows(title: str, rows: list[tuple[str, str]]) -> None:
    print(f"== {title} ==")
    w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{w}} : {v}")


def fail(msg: str, code: int) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# Consolas Windows (cp1252) no soportan todos los caracteres: nunca romper.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

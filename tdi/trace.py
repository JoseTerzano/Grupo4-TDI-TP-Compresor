"""Modo --trace: log paso a paso del Huffman dinámico (para archivos chicos)."""

from __future__ import annotations

import sys
from typing import TextIO

from .adaptive_huffman import INTERNAL, NYT_SYM, AdaptiveHuffmanTree


def sym_repr(s: int) -> str:
    if s == NYT_SYM:
        return "NYT"
    if s == INTERNAL:
        return "·"
    if 33 <= s <= 126:
        return f"'{chr(s)}'"
    return {10: "'\\n'", 13: "'\\r'", 9: "'\\t'", 32: "' '"}.get(s, f"0x{s:02x}")


def tree_str(tree: AdaptiveHuffmanTree) -> str:
    """Lista (número:peso:símbolo) desde la raíz hacia el NYT."""
    return "  ".join(f"{n}:{w}:{sym_repr(s)}" for n, w, s in reversed(tree.nodes()))


def make_tracer(out: TextIO = sys.stdout, limit: int | None = None,
                show_tree: bool = True):
    """Devuelve un callback compatible con encode()/decode()."""
    total_bits = [0]

    def tracer(i, byte, is_new, bits, tree):
        total_bits[0] += len(bits)
        if limit is not None and i >= limit:
            return
        kind = "NUEVO (NYT+8b)" if is_new else "conocido      "
        out.write(f"#{i:<4} {sym_repr(byte):>6}  {kind}  bits={bits:<22} "
                  f"({len(bits):>2} b, acum {total_bits[0]})\n")
        if show_tree:
            out.write(f"       árbol: {tree_str(tree)}\n")
    return tracer

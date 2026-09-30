"""Huffman dinámico FGK (Faller-Gallager-Knuth).

Representación
--------------
Árbol en arrays paralelos indexados por *número de nodo* (posición en el
orden de la propiedad de hermanos):

    weight[n]  peso del nodo que ocupa la posición n
    parent[n]  posición del padre
    left[n]    posición del hijo izquierdo (el derecho es left[n] + 1)
    symbol[n]  byte 0..255 si es hoja, INTERNAL o NYT_SYM
    leaf_of[s] posición de la hoja del byte s (-1 si aún no apareció)

Raíz = posición 512. El NYT empieza en la raíz; al dividirse en la posición
k crea (nuevo NYT = k-2, hoja = k-1) y k pasa a interno. Así el NYT siempre
tiene el número más bajo y los hermanos ocupan pares (par, impar):
hijo izquierdo = par (bit 0), derecho = impar (bit 1). Por eso el bit que
aporta un nodo a su código es simplemente `n & 1`.

Con 256 símbolos + NYT hay 257 hojas -> 2*257-1 = 513 posiciones (0..512).
El NYT se conserva aunque ya hayan aparecido los 256 bytes: simplifica el
código y su costo (una hoja de peso 0 al fondo del árbol) es despreciable.

Intercambio: se intercambia el *contenido* (subárbol) de dos posiciones; la
posición conserva su padre. Se actualizan parent[] de los hijos movidos y
leaf_of[] de las hojas movidas. Costo O(1).

Búsqueda del líder de bloque: escaneo hacia arriba mientras weight[m+1] sea
igual (centinela en weight[513]). Como los pesos son no decrecientes por
número, el bloque es contiguo; el costo es O(tamaño del bloque). Se eligió
sobre un dict leader[peso] porque el FGK rompe el orden transitoriamente
(hoja hermana del NYT incrementada antes que su padre), lo que complica
mantener el dict; en la práctica los bloques son chicos y el escaneo es
más rápido en CPython que el mantenimiento del dict.
"""

from __future__ import annotations

from typing import Callable, NamedTuple

from .bitio import BitReader, BitWriter
from .format import BitstreamExhaustedError, CorruptDataError

NSYM = 256
ROOT = 2 * NSYM            # 512
NODES = ROOT + 1           # 513 posiciones: 0..512
INTERNAL = -1
NYT_SYM = -2
_SENTINEL = 1 << 62


class AdaptiveHuffmanTree:
    __slots__ = ("weight", "parent", "left", "symbol", "leaf_of", "nyt",
                 "check")

    def __init__(self, check: bool = False) -> None:
        self.weight = [0] * (NODES + 1)
        self.weight[NODES] = _SENTINEL        # corta el escaneo del líder
        self.parent = [-1] * NODES
        self.left = [-1] * NODES
        self.symbol = [INTERNAL] * NODES
        self.symbol[ROOT] = NYT_SYM
        self.leaf_of = [-1] * NSYM
        self.nyt = ROOT
        self.check = check                    # verificar invariante (debug)

    # ------------------------------------------------------------ consultas
    def code_of(self, pos: int) -> tuple[int, int]:
        """Código (bits, longitud) del camino raíz->pos."""
        parent = self.parent
        code = 0
        length = 0
        while pos != ROOT:
            code |= (pos & 1) << length
            length += 1
            pos = parent[pos]
        return code, length

    def depth(self, pos: int) -> int:
        return self.code_of(pos)[1]

    def height(self) -> int:
        """Altura del árbol (profundidad máxima de hoja, NYT incluido)."""
        h = self.depth(self.nyt)
        for pos in self.leaf_of:
            if pos >= 0:
                h = max(h, self.depth(pos))
        return h

    def distinct_symbols(self) -> int:
        return sum(1 for p in self.leaf_of if p >= 0)

    def nodes(self) -> list[tuple[int, int, int]]:
        """(número, peso, símbolo) de las posiciones ocupadas, ascendente."""
        return [(n, self.weight[n], self.symbol[n])
                for n in range(self.nyt, NODES)]

    # ---------------------------------------------------------- modificación
    def add_symbol(self, s: int) -> int:
        """Divide el NYT: nuevo NYT (k-2) + hoja de `s` (k-1). Devuelve hoja."""
        k = self.nyt
        if k < 2:
            raise CorruptDataError("árbol lleno: símbolo nuevo imposible")
        nyt, leaf = k - 2, k - 1
        self.symbol[k] = INTERNAL
        self.left[k] = nyt
        self.parent[nyt] = self.parent[leaf] = k
        self.symbol[nyt] = NYT_SYM
        self.symbol[leaf] = s
        self.leaf_of[s] = leaf
        self.nyt = nyt
        return leaf

    def _swap(self, a: int, b: int) -> None:
        """Intercambia los subárboles que ocupan las posiciones a y b."""
        symbol, left = self.symbol, self.left
        sa, sb = symbol[a], symbol[b]
        la, lb = left[a], left[b]
        symbol[a], symbol[b] = sb, sa
        left[a], left[b] = lb, la
        # (los pesos son iguales por definición de bloque: no se tocan)
        for pos, s, l in ((a, sb, lb), (b, sa, la)):
            if s >= 0:
                self.leaf_of[s] = pos
            elif s == INTERNAL:
                self.parent[l] = self.parent[l + 1] = pos
            else:                              # NYT (no ocurre en FGK)
                self.nyt = pos

    def update(self, pos: int) -> None:
        """Incrementa la hoja `pos` y sus ancestros manteniendo hermanos."""
        weight, parent = self.weight, self.parent
        while True:
            w = weight[pos]
            m = pos
            while weight[m + 1] == w:          # líder = mayor número con peso w
                m += 1
            if m != pos and m != parent[pos]:
                self._swap(pos, m)
                pos = m
            weight[pos] = w + 1
            if pos == ROOT:
                break
            pos = parent[pos]
        if self.check:
            self.check_sibling_property()

    # ------------------------------------------------------------- invariante
    def check_sibling_property(self) -> None:
        w, p, left, sym = self.weight, self.parent, self.left, self.symbol
        for n in range(self.nyt, NODES):
            if n < ROOT:
                assert w[n] <= w[n + 1], f"peso decreciente en {n}"
                assert p[n] > n, f"padre de {n} con número menor"
                assert left[p[n]] == (n & ~1), f"{n} no es hijo de su padre"
            if sym[n] == INTERNAL:
                c = left[n]
                assert c & 1 == 0 and p[c] == n and p[c + 1] == n
                assert w[n] == w[c] + w[c + 1], f"peso interno {n} != suma"
            elif sym[n] >= 0:
                assert self.leaf_of[sym[n]] == n
        assert sym[self.nyt] == NYT_SYM and w[self.nyt] == 0


# ======================================================================
# Traza: callback(índice, byte, es_nuevo, bits_emitidos:str, árbol)
TraceFn = Callable[[int, int, bool, str, AdaptiveHuffmanTree], None]


class EncodeResult(NamedTuple):
    payload: bytes
    bit_length: int
    last_bits: int
    distinct: int
    height: int


def _bits_str(code: int, length: int) -> str:
    return format(code, f"0{length}b") if length else ""


def encode(data: bytes, trace: TraceFn | None = None,
           check: bool = False) -> EncodeResult:
    tree = AdaptiveHuffmanTree(check=check)
    bw = BitWriter()
    write = bw.write
    code_of = tree.code_of
    update = tree.update
    leaf_of = tree.leaf_of
    for i, b in enumerate(data):
        pos = leaf_of[b]
        if pos >= 0:
            code, length = code_of(pos)
            write(code, length)
            is_new = False
        else:
            code, length = code_of(tree.nyt)
            write(code, length)
            write(b, 8)
            is_new = True
            if trace is not None:               # NYT + byte crudo
                code, length = (code << 8) | b, length + 8
            pos = tree.add_symbol(b)
        update(pos)
        if trace is not None:
            trace(i, b, is_new, _bits_str(code, length), tree)
    return EncodeResult(bw.getvalue(), bw.bit_length, bw.last_bits,
                        tree.distinct_symbols(), tree.height())


def decode(payload: bytes, n: int, bit_length: int | None = None,
           trace: TraceFn | None = None, check: bool = False) -> bytes:
    """Reconstruye exactamente `n` bytes. Lanza CorruptDataError si el
    bitstream se agota, sobra, o es inconsistente."""
    reader = BitReader(payload, bit_length)
    out = bytearray()
    if n:
        tree = AdaptiveHuffmanTree(check=check)
        read_bit = reader.read_bit
        left, symbol, leaf_of = tree.left, tree.symbol, tree.leaf_of
        update = tree.update
        try:
            while len(out) < n:
                node = ROOT
                start = reader.position
                s = symbol[node]
                while s == INTERNAL:
                    node = left[node] + read_bit()
                    s = symbol[node]
                if s == NYT_SYM:
                    s = 0
                    for _ in range(8):
                        s = (s << 1) | read_bit()
                    if leaf_of[s] >= 0:
                        raise CorruptDataError(
                            f"byte 0x{s:02x} marcado nuevo pero ya existe "
                            f"(posición de salida {len(out)})")
                    node = tree.add_symbol(s)
                    is_new = True
                else:
                    is_new = False
                out.append(s)
                update(node)
                if trace is not None:
                    trace(len(out) - 1, s, is_new,
                          _bits_from(payload, start, reader.position), tree)
        except BitstreamExhaustedError as e:
            raise BitstreamExhaustedError(
                f"bitstream agotado: reconstruidos {len(out)} de {n} B") from e
    if reader.remaining:
        raise CorruptDataError(
            f"sobran {reader.remaining} bits tras reconstruir {n} B")
    return bytes(out)


def _bits_from(data: bytes, a: int, b: int) -> str:
    return "".join(str((data[p >> 3] >> (7 - (p & 7))) & 1) for p in range(a, b))

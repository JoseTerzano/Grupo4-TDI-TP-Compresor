"""Entrada/salida de bits MSB-first.

BitWriter acumula bits en un int y vuelca bytes completos a un bytearray
(nunca se concatenan strings '0'/'1'). BitReader lee bit a bit sobre un
buffer de bytes con una longitud en bits exacta.
"""

from __future__ import annotations

from .format import BitstreamExhaustedError


class BitWriter:
    """Escribe códigos de longitud variable, MSB primero."""

    __slots__ = ("_out", "_acc", "_nacc", "_total")

    def __init__(self) -> None:
        self._out = bytearray()
        self._acc = 0      # bits pendientes (a lo sumo ~40)
        self._nacc = 0     # cantidad de bits pendientes en _acc
        self._total = 0    # bits escritos en total

    def write(self, code: int, length: int) -> None:
        """Escribe los `length` bits menos significativos de `code`."""
        if length == 0:
            return
        acc = (self._acc << length) | code
        n = self._nacc + length
        self._total += length
        if n >= 32:
            k = n >> 3                     # bytes completos disponibles
            n -= k << 3
            self._out += (acc >> n).to_bytes(k, "big")
            acc &= (1 << n) - 1
        self._acc = acc
        self._nacc = n

    def write_bit(self, bit: int) -> None:
        self.write(bit & 1, 1)

    @property
    def bit_length(self) -> int:
        return self._total

    def getvalue(self) -> bytes:
        """Devuelve el buffer con el último byte rellenado con ceros."""
        out = bytearray(self._out)
        n = self._nacc
        if n:
            k = (n + 7) >> 3
            out += (self._acc << (k * 8 - n)).to_bytes(k, "big")
        return bytes(out)

    @property
    def last_bits(self) -> int:
        """Bits válidos del último byte: 1..8, o 0 si no se escribió nada."""
        if self._total == 0:
            return 0
        r = self._total & 7
        return r if r else 8


class BitReader:
    """Lee bits MSB-first de `data`, limitado a `bit_length` bits válidos."""

    __slots__ = ("_data", "_pos", "_nbits")

    def __init__(self, data: bytes, bit_length: int | None = None) -> None:
        if bit_length is None:
            bit_length = len(data) * 8
        if bit_length > len(data) * 8:
            raise ValueError("bit_length excede el tamaño del buffer")
        self._data = data
        self._pos = 0
        self._nbits = bit_length

    def read_bit(self) -> int:
        p = self._pos
        if p >= self._nbits:
            raise BitstreamExhaustedError(
                f"bitstream agotado tras {p} bits")
        self._pos = p + 1
        return (self._data[p >> 3] >> (7 - (p & 7))) & 1

    def read_bits(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.read_bit()
        return v

    @property
    def position(self) -> int:
        return self._pos

    @property
    def remaining(self) -> int:
        return self._nbits - self._pos

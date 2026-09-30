"""Round-trip: corpus, casos borde, aleatorios, BitIO e invariante de hermanos.

Ejecutar: python -m unittest discover -s tests -v
"""

import hashlib
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tdi import compress, decompress  # noqa: E402
from tdi.adaptive_huffman import AdaptiveHuffmanTree, decode, encode  # noqa: E402
from tdi.bitio import BitReader, BitWriter  # noqa: E402
from tdi.format import HEADER_SIZE, BitstreamExhaustedError  # noqa: E402

CORPUS = ROOT / "tests" / "corpus"
EXPECTED_SHA = {
    "prueba_1_pequena.txt": "8a0d7e04cc6347ca94cf03f7329ad7bf5881bfaff6d26da42e86166822c20051",
    "prueba_2_texto_natural.txt": "410d0deaf3cdfd3a51595d084445727ccc1c2c154b910738e0e32934bbbae403",
    "prueba_3_alta_repeticion.txt": "a54f4a85a8695e1bec7cf49603301d97bd08c89f98dddb09fb0605fa1f88e36e",
    "prueba_4_baja_repeticion.txt": "7b7b0ac6050531d99b338e2db14c188565bbf12f4b08a97b4398b7eda28b6d61",
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def roundtrip(tc: unittest.TestCase, data: bytes, check: bool = False) -> bytes:
    blob = compress(data, check=check).blob
    out, header = decompress(blob, check=check)
    tc.assertEqual(header.original_size, len(data))
    tc.assertEqual(out, data)
    tc.assertEqual(sha(out), sha(data))
    return blob


class TestBitIO(unittest.TestCase):
    def test_write_read(self):
        rng = random.Random(1)
        items = [(rng.getrandbits(n), n) for n in (rng.randint(0, 20) for _ in range(5000))]
        bw = BitWriter()
        for code, n in items:
            bw.write(code, n)
        total = sum(n for _, n in items)
        self.assertEqual(bw.bit_length, total)
        data = bw.getvalue()
        self.assertEqual(len(data), (total + 7) // 8)
        br = BitReader(data, total)
        for code, n in items:
            self.assertEqual(br.read_bits(n), code)
        self.assertEqual(br.remaining, 0)
        with self.assertRaises(BitstreamExhaustedError):
            br.read_bit()

    def test_msb_first_and_last_bits(self):
        bw = BitWriter()
        bw.write(0b101, 3)
        self.assertEqual(bw.getvalue(), bytes([0b10100000]))
        self.assertEqual(bw.last_bits, 3)
        bw.write(0b11111, 5)
        self.assertEqual(bw.last_bits, 8)
        self.assertEqual(BitWriter().last_bits, 0)


class TestSiblingProperty(unittest.TestCase):
    def test_invariant_every_update(self):
        rng = random.Random(7)
        for data in (b"ABRACADABRA ABRACADABRA\nTOMATOMATOMA$",
                     bytes(range(256)) * 3,
                     bytes(rng.choice(b"aaaabbbcdeffff\x00\xff") for _ in range(4000)),
                     bytes(rng.getrandbits(8) for _ in range(6000))):
            roundtrip(self, data, check=True)

    def test_initial_tree(self):
        t = AdaptiveHuffmanTree()
        t.check_sibling_property()
        self.assertEqual(t.code_of(t.nyt), (0, 0))

    def test_corpus_small_invariant(self):
        roundtrip(self, (CORPUS / "prueba_1_pequena.txt").read_bytes(), check=True)


class TestCorpus(unittest.TestCase):
    def test_corpus_sha_matches_readme(self):
        for name, h in EXPECTED_SHA.items():
            self.assertEqual(sha((CORPUS / name).read_bytes()), h, name)

    def test_corpus_roundtrip_and_bound(self):
        import math
        from collections import Counter
        for name in EXPECTED_SHA:
            data = (CORPUS / name).read_bytes()
            blob = roundtrip(self, data)
            # payload no puede superar la cota orden-0 (costo de aprendizaje
            # aparte): bits >= n·H0 (Huffman nunca baja de la entropía)
            n = len(data)
            h0 = -sum(c / n * math.log2(c / n) for c in Counter(data).values())
            payload_bits = (len(blob) - HEADER_SIZE) * 8
            self.assertGreaterEqual(payload_bits + 8, n * h0, name)


class TestEdgeCases(unittest.TestCase):
    def test_empty(self):
        blob = roundtrip(self, b"")
        self.assertEqual(len(blob), HEADER_SIZE)

    def test_one_byte(self):
        for b in (0, 65, 255):
            blob = roundtrip(self, bytes([b]))
            self.assertEqual(len(blob), HEADER_SIZE + 1)

    def test_repeated_symbol(self):
        blob = roundtrip(self, b"x" * 10000)
        # 8 bits crudos + 1 bit por símbolo restante
        self.assertEqual(len(blob), HEADER_SIZE + (8 + 9999 + 7) // 8)

    def test_all_256(self):
        roundtrip(self, bytes(range(256)), check=True)
        roundtrip(self, bytes(range(255, -1, -1)) * 4)

    def test_urandom_expands_slightly(self):
        data = os.urandom(100_000)
        blob = roundtrip(self, data)
        self.assertGreater(len(blob), len(data))
        self.assertLess(len(blob), len(data) * 1.01)

    def test_random_seeds(self):
        for seed in range(8):
            rng = random.Random(seed)
            n = rng.randint(0, 3000)
            k = rng.randint(1, 256)
            alphabet = rng.sample(range(256), k)
            data = bytes(rng.choice(alphabet) for _ in range(n))
            roundtrip(self, data)

    def test_crlf_and_binary_untouched(self):
        roundtrip(self, b"linea\r\notra\r\n\x00\x1a\xc3\xb1")

    def test_encode_decode_memory(self):
        data = b"TOMATOMATOMA$" * 10
        enc = encode(data)
        self.assertEqual(decode(enc.payload, len(data), enc.bit_length), data)


if __name__ == "__main__":
    unittest.main()

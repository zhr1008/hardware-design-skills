import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts import check_publication as publication


def chunk(kind, data=b""):
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))


def image(*, metadata=b"", compressed=None, width=1, height=1):
    header = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    if compressed is None:
        compressed = zlib.compress(b"\x00\xd0\x80\x40")
    return publication.PNG_SIGNATURE + header + metadata + chunk(b"IDAT", compressed) + chunk(b"IEND")


class TestPublicationDiagram(unittest.TestCase):
    def test_valid_png_at_exact_path_is_allowed(self):
        self.assertTrue(publication.valid_publication_diagram(image()))
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            diagram = repo / publication.PUBLICATION_DIAGRAM
            diagram.parent.mkdir(parents=True)
            diagram.write_bytes(image())
            publication.git(repo, "add", "--", publication.PUBLICATION_DIAGRAM)
            self.assertEqual(publication.scan(repo, staged=True, tree=None), (1, []))

            other = "docs/architecture/other.png"
            (repo / other).write_bytes(diagram.read_bytes())
            publication.git(repo, "add", "--", other)
            self.assertEqual(publication.scan(repo, staged=True, tree=None), (2, [
                {"path": other, "line": 0, "rule": "binary-or-unsupported-text-encoding"},
            ]))

            diagram.write_bytes(image(metadata=chunk(b"tEXt", b"Comment\x00example")))
            publication.git(repo, "add", "--", publication.PUBLICATION_DIAGRAM)
            _, findings = publication.scan(repo, staged=True, tree=None)
            self.assertIn({
                "path": publication.PUBLICATION_DIAGRAM,
                "line": 0,
                "rule": "invalid-publication-diagram-png",
            }, findings)

    def test_rejects_metadata_even_when_crc_and_pixel_stream_are_valid(self):
        for kind in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"iCCP", b"sRGB"):
            with self.subTest(kind=kind):
                self.assertFalse(publication.valid_publication_diagram(image(metadata=chunk(kind, b"\x00"))))

    def test_rejects_bad_chunks_or_pixel_streams(self):
        valid = image()
        wrong_crc = valid[:-1] + bytes([valid[-1] ^ 1])
        cases = {
            "signature": b"not a PNG" + valid,
            "truncated": valid[:-1],
            "CRC mismatch": wrong_crc,
            "appended file data": valid + b"trailing data",
            "no pixels": image(compressed=b""),
            "non-zlib pixels": image(compressed=b"bad zlib data"),
            "hidden data after zlib eof": image(compressed=zlib.compress(b"\x00abc") + b"suffix"),
            "second zlib stream": image(compressed=zlib.compress(b"\x00abc") + zlib.compress(b"extra")),
            "too many pixels": image(compressed=zlib.compress(b"\x00abcdef")),
            "too few pixels": image(compressed=zlib.compress(b"\x00ab")),
            "invalid row filter": image(compressed=zlib.compress(b"\x05abc")),
            "zero width": image(width=0),
            "huge image": image(width=publication.MAX_DIAGRAM_AXIS + 1),
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertFalse(publication.valid_publication_diagram(data))


if __name__ == "__main__":
    unittest.main()

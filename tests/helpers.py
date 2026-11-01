"""Batches made in memory for the tests: a .zip with recipes.json and
photos/, and image headers just big enough to be measured."""

import io
import json
import struct
import zipfile


def jpeg(width: int, height: int) -> bytes:
    """A JPEG with only its SOF0 header: enough to read its size."""
    sof = (
        b"\xff\xc0"
        + struct.pack(">HBHHB", 17, 8, height, width, 3)
        + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def png(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(ihdr))
        + b"IHDR"
        + ihdr
        + b"\x00\x00\x00\x00"
    )


def make_zip(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            if isinstance(content, str):
                content = content.encode("utf-8")
            archive.writestr(path, content)
    return buffer.getvalue()


def recipe(name="Tortilla de patatas", **fields):
    base = {
        "name": name,
        "author": "Cocina de casa",
        "url": "https://www.youtube.com/watch?v=LEqs_Crvark",
        "category": "huevos",
        "preparationTime": "40 min",
        "ingredients": [
            {"name": "Patata", "quantity": "500 g"},
            {"name": "Huevo", "quantity": "4"},
        ],
        "preparationSteps": ["Fríe las patatas.", "Cuaja la tortilla."],
    }
    base.update(fields)
    return base


def batch(*recipes, version=1):
    return {"version": version, "recipes": list(recipes)}

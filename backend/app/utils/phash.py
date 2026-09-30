"""
app/utils/phash.py
-------------------
Difference hash (dHash) for near-duplicate image detection. 16x16 (256 bit).
Measured on this project's dataset: re-encoded / resized / brightened /
slightly cropped copies of one photo differ by <= ~9 bits, while 7,140 pairs of
unrelated pothole images differed by >= 13 bits — so a threshold of 12 gives
no false positives there. (An 8x8 hash did NOT separate them well.)
"""
from PIL import Image


def dhash(img: Image.Image, hash_size: int = 16) -> str:
    """256-bit difference hash returned as a 64-char hex string."""
    small = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            left = px[row * (hash_size + 1) + col]
            right = px[row * (hash_size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:0{hash_size * hash_size // 4}x}"


def hamming(hex_a: str, hex_b: str) -> int:
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")

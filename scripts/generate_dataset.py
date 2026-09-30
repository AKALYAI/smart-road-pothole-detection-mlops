"""
generate_dataset.py
--------------------
Generates a ~200 image synthetic road dataset (pothole vs normal road) in
YOLOv8 format. This stands in for a real-world collected dataset (e.g. from
Roboflow / Kaggle pothole datasets) so the full MLOps pipeline in this repo
(training -> MLflow tracking -> DVC versioning -> FastAPI serving) can be
run end-to-end offline, deterministically, and reproducibly.

To use a REAL dataset instead:
  1. Drop your images into data/pothole_dataset/images/{train,val,test}
  2. Drop matching YOLO-format .txt labels into
     data/pothole_dataset/labels/{train,val,test}
  3. Keep class 0 = "pothole" (add more classes in data.yaml if needed)
  4. Skip this script and go straight to scripts/train.py

Usage:
    python scripts/generate_dataset.py --count 200 --out data/pothole_dataset
"""
import argparse
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

random.seed(42)

IMG_SIZE = 640
CLASS_NAMES = ["pothole"]


def _road_background(draw, w, h):
    """Paint an asphalt-like gradient background with a lane marking."""
    base = random.randint(55, 80)
    for y in range(h):
        shade = base + int(10 * (y / h)) + random.randint(-2, 2)
        draw.line([(0, y), (w, y)], fill=(shade, shade, shade + 2))
    # occasional lane marking
    if random.random() < 0.6:
        x = random.randint(w // 3, 2 * w // 3)
        dash_h = 40
        y = 0
        while y < h:
            draw.rectangle([x - 8, y, x + 8, y + dash_h], fill=(230, 230, 210))
            y += dash_h * 2
    # some cracks / noise texture
    for _ in range(random.randint(5, 15)):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = x1 + random.randint(-60, 60), y1 + random.randint(-60, 60)
        c = base - random.randint(5, 15)
        draw.line([(x1, y1), (x2, y2)], fill=(c, c, c), width=1)


def _draw_pothole(draw, cx, cy, r):
    """Draw a dark, irregular pothole blob with a lighter rim (shadow effect)."""
    # outer rim (lighter, worn edge)
    rim_pts = []
    for a in range(0, 360, 18):
        rr = r * random.uniform(0.95, 1.25)
        import math
        rim_pts.append((cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))))
    draw.polygon(rim_pts, fill=(90, 82, 70))

    # inner dark hole (irregular polygon)
    pts = []
    for a in range(0, 360, 18):
        rr = r * random.uniform(0.55, 0.9)
        import math
        pts.append((cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))))
    dark = random.randint(10, 35)
    draw.polygon(pts, fill=(dark, dark, dark))

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def make_image(path, has_pothole, n_potholes=1):
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (70, 70, 70))
    draw = ImageDraw.Draw(img)
    _road_background(draw, IMG_SIZE, IMG_SIZE)

    boxes = []
    if has_pothole:
        for _ in range(n_potholes):
            r = random.randint(35, 90)
            cx = random.randint(r + 20, IMG_SIZE - r - 20)
            cy = random.randint(r + 20, IMG_SIZE - r - 20)
            x1, y1, x2, y2 = _draw_pothole(draw, cx, cy, r)
            x1, y1 = max(0, x1 - 4), max(0, y1 - 4)
            x2, y2 = min(IMG_SIZE, x2 + 4), min(IMG_SIZE, y2 + 4)
            boxes.append((x1, y1, x2, y2))

    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0, 0.8)))
    img.save(path, quality=90)
    return boxes


def to_yolo_label(box, img_w, img_h, cls=0):
    x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2) / img_w
    cy = ((y1 + y2) / 2) / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--out", type=str, default="data/pothole_dataset")
    ap.add_argument("--pothole_ratio", type=float, default=0.6)
    args = ap.parse_args()

    out = Path(args.out)
    splits = {"train": 0.7, "val": 0.2, "test": 0.1}
    counts = {k: int(args.count * v) for k, v in splits.items()}
    # fix rounding so total == args.count
    diff = args.count - sum(counts.values())
    counts["train"] += diff

    idx = 0
    manifest = []
    for split, n in counts.items():
        img_dir = out / "images" / split
        lbl_dir = out / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        n_pothole = int(n * args.pothole_ratio)
        flags = [True] * n_pothole + [False] * (n - n_pothole)
        random.shuffle(flags)

        for has_pothole in flags:
            idx += 1
            fname = f"road_{idx:04d}.jpg"
            img_path = img_dir / fname
            n_p = random.choice([1, 1, 1, 2]) if has_pothole else 0
            boxes = make_image(img_path, has_pothole, n_p)

            lbl_path = lbl_dir / fname.replace(".jpg", ".txt")
            with open(lbl_path, "w") as f:
                for b in boxes:
                    f.write(to_yolo_label(b, IMG_SIZE, IMG_SIZE) + "\n")

            manifest.append((split, fname, has_pothole, len(boxes)))

    # data.yaml for YOLOv8
    yaml_path = out / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(
            f"path: {out.resolve()}\n"
            f"train: images/train\n"
            f"val: images/val\n"
            f"test: images/test\n"
            f"nc: {len(CLASS_NAMES)}\n"
            f"names: {CLASS_NAMES}\n"
        )

    print(f"Generated {idx} images across {list(counts.keys())} -> {counts}")
    print(f"data.yaml written to {yaml_path}")


if __name__ == "__main__":
    main()

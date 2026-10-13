from pathlib import Path
from PIL import Image

source = Path(
    r"D:\IMVU-Music-Bot\assets\crowbot.png"
)

destination = Path(
    r"D:\IMVU-Music-Bot\assets\crowbot.ico"
)

if not source.exists():
    raise FileNotFoundError(
        f"Source image not found: {source}"
    )

image = Image.open(source).convert("RGBA")

# Windows application icon resolutions.
sizes = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]

image.save(
    destination,
    format="ICO",
    sizes=sizes,
)

print()
print("[OK] CrowBot icon created:")
print(destination)
print()
print("Icon sizes:")
for size in sizes:
    print(f"  {size[0]}x{size[1]}")

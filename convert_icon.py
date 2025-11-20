import struct

# Read ICO file and extract PNG data
with open('icon.ico', 'rb') as f:
    # ICO header: reserved(2) + type(2) + count(2)
    header = f.read(6)
    reserved, ico_type, count = struct.unpack('<HHH', header)

    print(f"ICO file contains {count} images")

    # Find largest image
    best_idx = 0
    best_size = 0
    entries = []

    for i in range(count):
        # Directory entry: width(1) + height(1) + colors(1) + reserved(1) + planes(2) + bpp(2) + size(4) + offset(4)
        entry = f.read(16)
        width, height, colors, res, planes, bpp, size, offset = struct.unpack('<BBBBHHII', entry)

        # 0 means 256
        if width == 0:
            width = 256
        if height == 0:
            height = 256

        entries.append((width, height, size, offset))

        if width * height > best_size:
            best_size = width * height
            best_idx = i

    # Extract largest image
    width, height, size, offset = entries[best_idx]
    print(f"Extracting image {best_idx}: {width}x{height}, {size} bytes at offset {offset}")

    f.seek(offset)
    image_data = f.read(size)

    # Check if it's PNG (starts with PNG signature)
    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
        print("Image is PNG format")
        with open('icon_temp.png', 'wb') as out:
            out.write(image_data)
        print("Saved as icon_temp.png")
    else:
        print("Image is BMP format (not PNG)")

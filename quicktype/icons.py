"""Shared icon rendering helpers for QuickType."""


def create_app_icon_image(size: int = 64):
    """Build the shared QuickType brand icon as a PIL image."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (size, size), color=(15, 45, 180))
    draw = ImageDraw.Draw(image)

    accent_height = max(size // 6, 1)
    draw.rectangle((0, 0, size - 1, accent_height), fill=(255, 220, 0))

    font_size = max(int(size * 0.7), 14)
    try:
        font = ImageFont.truetype("consolab.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("segoeuib.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    text = ">_"
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top
    except Exception:
        text_width = int(size * 0.5)
        text_height = int(size * 0.3)

    text_x = max((size - text_width) // 2 - 2, 0)
    text_y = max((size - text_height) // 2 - 2, 0)
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))
    return image

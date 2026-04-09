import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Default Chinese font path
CHINESE_FONT_REGULAR = os.path.join("fonts", "NotoSansCJKsc-Regular.otf")
CHINESE_FONT_BOLD = os.path.join("fonts", "NotoSansCJKsc-Bold.otf")


def add_chinese_subtitle(
    image_path: str,
    chinese_text: str,
    output_path: str = None,
    font_size: int = 32,
    padding: int = 20,
    max_width_chars: int = 25,
    bg_color: tuple = (0, 0, 0, 180),
    text_color: tuple = (255, 255, 255, 255),
) -> str:
    """Add a Chinese subtitle bar below an existing screenshot image.

    Args:
        image_path: Path to the original screenshot image.
        chinese_text: The Chinese text to render as subtitle.
        output_path: Path to save the output image. Defaults to overwriting input.
        font_size: Font size for the Chinese text.
        padding: Padding around the text in the subtitle bar.
        max_width_chars: Maximum characters per line before wrapping.
        bg_color: Background color of the subtitle bar (RGBA).
        text_color: Text color (RGBA).

    Returns:
        The output path of the saved image.
    """
    if output_path is None:
        output_path = image_path

    original = Image.open(image_path).convert("RGBA")
    orig_w, orig_h = original.size

    font = ImageFont.truetype(CHINESE_FONT_BOLD, font_size)

    lines = _wrap_chinese_text(chinese_text, max_width_chars)

    # Calculate subtitle bar dimensions
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 8
    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    subtitle_height = total_text_height + padding * 2

    # Create new image with subtitle bar
    new_h = orig_h + subtitle_height
    new_image = Image.new("RGBA", (orig_w, new_h), (0, 0, 0, 0))
    new_image.paste(original, (0, 0))

    # Draw semi-transparent background bar
    subtitle_bar = Image.new("RGBA", (orig_w, subtitle_height), bg_color)
    new_image.paste(subtitle_bar, (0, orig_h), subtitle_bar)

    # Draw text on the subtitle bar
    draw = ImageDraw.Draw(new_image)
    y = orig_h + padding
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (orig_w - line_w) // 2  # center the text
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_heights[i] + line_spacing

    new_image.save(output_path)
    return output_path


def _wrap_chinese_text(text: str, max_chars: int) -> list:
    """Wrap Chinese text into lines of max_chars characters each.

    Chinese text doesn't have spaces for word wrapping, so we break at
    character boundaries.

    Args:
        text: The Chinese text to wrap.
        max_chars: Maximum characters per line.

    Returns:
        List of lines.
    """
    text = text.strip()
    if not text:
        return [""]

    lines = []
    while text:
        if len(text) <= max_chars:
            lines.append(text)
            break
        # Try to find a natural break point (punctuation)
        break_idx = max_chars
        for punct in "。！？；，、":
            idx = text.rfind(punct, 0, max_chars)
            if idx > max_chars // 2:
                break_idx = idx + 1
                break
        lines.append(text[:break_idx])
        text = text[break_idx:].strip()

    return lines

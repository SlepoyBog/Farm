import logging
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

IMAGE_WIDTH = 800
PADDING_TOP = 40
PADDING_SIDE = 40
TITLE_FONT_SIZE = 28
BODY_FONT_SIZE = 18
LINE_SPACING = 6
OVERLAY_ALPHA = 180
MAX_BODY_CHARS = 2500

_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/times.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font
                logger.debug(f"Using font: {path}")
                return font
            except Exception:
                continue

    try:
        import subprocess
        result = subprocess.run(
            ["fc-match", "-v", "sans"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "file:" in line:
                path = line.strip().split('"')[1]
                if os.path.exists(path):
                    font = ImageFont.truetype(path, size)
                    _FONT_CACHE[size] = font
                    return font
    except Exception:
        pass

    logger.warning("No TTF font found, using default Pillow font")
    return None


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if not lines:
        lines = [text]
    return lines


def _strip_html(html: str) -> str:
    text = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    import html as html_module
    text = html_module.unescape(text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    return text.strip()


def render_article_image(
    background_url: str,
    title: str,
    article_html: str,
    output_dir: str = "output",
) -> Optional[str]:
    try:
        logger.info("Rendering article image via Pillow...")

        resp = requests.get(background_url, timeout=15)
        resp.raise_for_status()
        bg = Image.open(BytesIO(resp.content)).convert("RGB")
        bg = bg.resize((IMAGE_WIDTH, int(IMAGE_WIDTH * bg.height / bg.width)), Image.LANCZOS)

        overlay = Image.new("RGBA", bg.size, (0, 0, 0, OVERLAY_ALPHA))
        bg.paste(overlay, (0, 0), overlay)

        draw = ImageDraw.Draw(bg)

        title_font = _get_font(TITLE_FONT_SIZE)
        body_font = _get_font(BODY_FONT_SIZE)

        y = PADDING_TOP
        max_text_width = IMAGE_WIDTH - PADDING_SIDE * 2

        if title_font:
            title_lines = _wrap_text(title, title_font, max_text_width)
            for line in title_lines:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                x = (IMAGE_WIDTH - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, font=title_font, fill="white")
                y += (bbox[3] - bbox[1]) + LINE_SPACING + 6
        else:
            draw.text((PADDING_SIDE, y), title, fill="white")
            y += 40

        y += 16

        body = _strip_html(article_html)
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS].rsplit(".", 1)[0] + "."

        paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
        for para in paragraphs:
            if y > bg.height - 60:
                if body_font:
                    bbox = draw.textbbox((0, 0), "…читать далее", font=body_font)
                    draw.text((PADDING_SIDE, y), "…читать далее", font=body_font, fill="#aaaaaa")
                else:
                    draw.text((PADDING_SIDE, y), "…читать далее", fill="#aaaaaa")
                break

            lines = _wrap_text(para, body_font, max_text_width) if body_font else [para]
            for line in lines:
                draw.text((PADDING_SIDE, y), line, font=body_font or ImageFont.load_default(), fill="white")
                if body_font:
                    bbox = draw.textbbox((0, 0), line, font=body_font)
                    y += (bbox[3] - bbox[1]) + LINE_SPACING
                else:
                    y += 22
            y += 8

        canvas = Image.new("RGB", (IMAGE_WIDTH, y + PADDING_TOP), (0, 0, 0))
        copy_h = min(y + PADDING_TOP, bg.height)
        canvas.paste(bg.crop((0, 0, IMAGE_WIDTH, copy_h)), (0, 0))

        os.makedirs(output_dir, exist_ok=True)
        slug = re.sub(r'[^\w-]', '_', title)[:40].lower().strip("_")
        out_path = Path(output_dir) / f"rendered_{slug}.png"
        canvas.save(str(out_path), format="PNG")

        logger.info(f"Article image rendered: {out_path}")
        return str(out_path)

    except Exception as e:
        logger.error(f"Failed to render article image: {e}", exc_info=True)
        return None

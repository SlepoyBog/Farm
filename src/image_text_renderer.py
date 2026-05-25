import logging
import os
import re
import tempfile
from io import BytesIO
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
OVERLAY_ALPHA = 160

_FONT_CACHE: dict[str, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/times.ttf",
    ]
    for path in candidates:
        if path in _FONT_CACHE:
            return _FONT_CACHE[path]
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[path] = font
                return font
            except Exception:
                continue
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
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _get_body_text(html: str) -> str:
    text = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    import html as html_module
    text = html_module.unescape(text)
    text = text.strip()
    if len(text) > 2000:
        text = text[:2000] + '…'
    return text


def render_article_image(
    background_url: str,
    title: str,
    article_html: str,
) -> Optional[str]:
    try:
        logger.info("Rendering article image…")

        resp = requests.get(background_url, timeout=15)
        resp.raise_for_status()
        bg = Image.open(BytesIO(resp.content)).convert("RGB")
        bg = bg.resize((IMAGE_WIDTH, int(IMAGE_WIDTH * bg.height / bg.width)), Image.LANCZOS)

        draw = ImageDraw.Draw(bg, "RGBA")
        overlay = Image.new("RGBA", bg.size, (0, 0, 0, OVERLAY_ALPHA))
        bg.paste(overlay, (0, 0), overlay)

        draw = ImageDraw.Draw(bg)

        title_font = _get_font(TITLE_FONT_SIZE) or ImageFont.load_default()
        body_font = _get_font(BODY_FONT_SIZE) or ImageFont.load_default()

        y = PADDING_TOP
        max_text_width = IMAGE_WIDTH - PADDING_SIDE * 2

        title_lines = _wrap_text(title, title_font, max_text_width)
        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            x = (IMAGE_WIDTH - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, font=title_font, fill="white")
            y += (bbox[3] - bbox[1]) + LINE_SPACING + 4

        y += 12

        body = _get_body_text(article_html)
        paragraphs = body.split("\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                y += 8
                continue
            lines = _wrap_text(para, body_font, max_text_width)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=body_font)
                draw.text((PADDING_SIDE, y), line, font=body_font, fill="white")
                y += (bbox[3] - bbox[1]) + LINE_SPACING

        canvas = Image.new("RGB", (IMAGE_WIDTH, y + PADDING_TOP), (0, 0, 0))
        canvas.paste(bg.crop((0, 0, IMAGE_WIDTH, min(y + PADDING_TOP, bg.height))), (0, 0))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir="output") as tmp:
            canvas.save(tmp, format="PNG")
            tmp_path = tmp.name

        logger.info(f"Article image rendered: {tmp_path}")
        return tmp_path

    except Exception as e:
        logger.error(f"Failed to render article image: {e}", exc_info=True)
        return None

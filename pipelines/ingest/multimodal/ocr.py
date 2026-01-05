"""图片 OCR — CPU；可选依赖 rapidocr-onnxruntime，未安装则跳过."""

from __future__ import annotations

from pathlib import Path


def ocr_image(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        try:
            import pytesseract
            from PIL import Image

            return pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng").strip()
        except ImportError:
            return ""
    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    return "\n".join(line[1] for line in result if len(line) > 1)


def ocr_images_in_markdown(text: str, base_dir: Path) -> str:
    """解析 ![](path) 并 OCR 本地图片."""
    import re

    extra: list[str] = []
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        rel = m.group(1).strip()
        if rel.startswith("http"):
            continue
        img = (base_dir / rel).resolve()
        txt = ocr_image(img)
        if txt:
            extra.append(f"（OCR {rel}）{txt[:500]}")
    if extra:
        return text + "\n\n" + "\n".join(extra)
    return text

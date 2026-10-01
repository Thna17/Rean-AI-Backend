from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FONT = "/System/Library/Fonts/Helvetica.ttc"


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def font(size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size=size, index=index)


intro = Image.new("RGBA", (1920, 1080), "#07111f")
draw = ImageDraw.Draw(intro, "RGBA")

# A clean title card avoids showing an unrelated question behind the demo prompt.
for y in range(1080):
    blend = y / 1079
    draw.line((0, y, 1920, y), fill=(7, round(17 + 15 * blend), round(31 + 32 * blend), 255))

logo = Image.open(ROOT.parent / "ai_tutor" / "assets" / "images" / "ai_tutor_logo.png").convert("RGBA")
logo.thumbnail((210, 210), Image.Resampling.LANCZOS)
intro.alpha_composite(logo, (112, 92))

draw.rounded_rectangle((110, 350, 1810, 715), radius=38, fill=(5, 13, 29, 238), outline=(53, 217, 255, 255), width=4)
draw.text((165, 405), "GRADE 12 LIMITS", font=font(30), fill="#35d9ff")
draw.text((165, 480), "Find the limit", font=font(72), fill="white")
draw.text((165, 585), "(x^2 - 4) / (x - 2)   as x approaches 2", font=font(46), fill="#dce8f8")

draw.text((115, 790), "FROM QUESTION TO UNDERSTANDING", font=font(34), fill="#35d9ff")
draw.text((115, 850), "One visual flow. Every step explained.", font=font(52), fill="white")
draw.text((115, 945), "English + Khmer  |  Verified Grade 10-12 STEM", font=font(30), fill="#c8d5ea")
intro.convert("RGB").save(ROOT / "intro.png", quality=95)

badge = Image.new("RGBA", (590, 80), (0, 0, 0, 0))
badge_draw = ImageDraw.Draw(badge, "RGBA")
badge_draw.rounded_rectangle((0, 0, 590, 80), radius=22, fill=(7, 19, 35, 226))
badge_draw.text((36, 24), "LIVE BOARD  •  GRADE 12 LIMITS", font=font(27), fill="#35d9ff")
badge.save(ROOT / "badge.png")

outro = Image.new("RGBA", (1920, 1080), "#07111f")
logo = Image.open(ROOT.parent / "ai_tutor" / "assets" / "images" / "ai_tutor_logo.png").convert("RGBA")
logo.thumbnail((300, 300), Image.Resampling.LANCZOS)
outro.alpha_composite(logo, ((1920 - logo.width) // 2, 170))
outro_draw = ImageDraw.Draw(outro)

def centered(text: str, y: int, text_font: ImageFont.FreeTypeFont, fill: str) -> None:
    box = outro_draw.textbbox((0, 0), text, font=text_font)
    outro_draw.text(((1920 - (box[2] - box[0])) / 2, y), text, font=text_font, fill=fill)


centered("REAN AI", 585, font(76), "#35d9ff")
centered("Verified visual tutoring for Cambodian STEM", 700, font(38), "white")
centered("Ask. Watch. Understand.", 775, font(30), "#b8c7de")
outro.convert("RGB").save(ROOT / "outro.png", quality=95)

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT_HELVETICA = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
BG_DARK = (7, 17, 31)

def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    index = 1 if bold else 0
    return ImageFont.truetype(FONT_HELVETICA, size=size, index=index)

def create_gradient_canvas(width: int = 1920, height: int = 1080) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), "#07111f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    for y in range(height):
        blend = y / (height - 1)
        draw.line((0, y, width, y), fill=(7, round(17 + 16 * blend), round(31 + 35 * blend), 255))
    return canvas

def make_title_slide(stage_num: str, title: str, subtitle: str, detail_items: list[str]) -> Image.Image:
    img = create_gradient_canvas()
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Header badge
    draw.rounded_rectangle((100, 70, 480, 130), radius=16, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    draw.text((120, 85), f"REAN AI DEMO · {stage_num}", font=get_font(26, True), fill="#35d9ff")
    
    # Title & Subtitle
    draw.text((100, 160), title, font=get_font(68, True), fill="white")
    draw.text((100, 250), subtitle, font=get_font(34), fill="#a5c4e8")
    
    # Detail Card Box
    draw.rounded_rectangle((100, 340, 1820, 920), radius=28, fill=(5, 14, 28, 230), outline=(30, 60, 95, 255), width=3)
    
    y = 390
    for idx, item in enumerate(detail_items, 1):
        # Bullet circle
        draw.ellipse((140, y + 10, 176, y + 46), fill=(53, 217, 255, 40), outline="#35d9ff", width=2)
        draw.text((151, y + 13), str(idx), font=get_font(22, True), fill="#35d9ff")
        
        parts = item.split(":", 1)
        if len(parts) == 2:
            draw.text((200, y), parts[0] + ":", font=get_font(32, True), fill="#ffffff")
            box = draw.textbbox((0, 0), parts[0] + ": ", font=get_font(32, True))
            draw.text((200 + (box[2] - box[0]), y), parts[1], font=get_font(32), fill="#c5d8f2")
        else:
            draw.text((200, y), item, font=get_font(32), fill="#c5d8f2")
        y += 85
        
    return img

def compose_board_showcase(stage_num: str, title: str, subtitle: str, board_img_path: Path) -> Image.Image:
    canvas = create_gradient_canvas()
    draw = ImageDraw.Draw(canvas, "RGBA")
    
    # Top banner
    draw.rounded_rectangle((80, 50, 440, 105), radius=14, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    draw.text((100, 65), f"STAGE {stage_num} · {title.upper()}", font=get_font(24, True), fill="#35d9ff")
    
    draw.text((80, 125), title, font=get_font(52, True), fill="white")
    draw.text((80, 195), subtitle, font=get_font(28), fill="#9fc2ea")
    
    # Board Image Frame
    if board_img_path.exists():
        raw_board = Image.open(board_img_path).convert("RGBA")
        target_w, target_h = 1760, 780
        scale = min(target_w / raw_board.width, target_h / raw_board.height)
        scaled_w = round(raw_board.width * scale)
        scaled_h = round(raw_board.height * scale)
        resized = raw_board.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        
        pos_x = 80 + (target_w - scaled_w) // 2
        pos_y = 250 + (target_h - scaled_h) // 2
        
        # Shadow / border
        draw.rounded_rectangle((pos_x - 6, pos_y - 6, pos_x + scaled_w + 6, pos_y + scaled_h + 6), radius=20, fill=(3, 8, 16, 255), outline=(53, 217, 255, 180), width=3)
        canvas.alpha_composite(resized, (pos_x, pos_y))
    
    return canvas

def make_quiz_slide() -> Image.Image:
    img = create_gradient_canvas()
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Badge
    draw.rounded_rectangle((100, 60, 460, 115), radius=14, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    draw.text((120, 75), "STAGE 4 · STUDENT PRACTICE", font=get_font(24, True), fill="#35d9ff")
    
    draw.text((100, 140), "Targeted Practice Quiz & Instant Grading", font=get_font(54, True), fill="white")
    draw.text((100, 215), "Grade 12 Physics: Kinematics (ចលនាត្រង់ស្ទុះស្មើ)", font=get_font(30), fill="#a5c4e8")
    
    # Question Card 1
    draw.rounded_rectangle((100, 280, 1260, 560), radius=22, fill=(10, 24, 45, 240), outline=(40, 80, 120, 255), width=2)
    draw.text((130, 310), "Q1: A car accelerates from rest at 2 m/s² for 5 s. What is final velocity?", font=get_font(28, True), fill="white")
    
    # Choices
    choices = [("A", "10 m/s  (Correct ✓)", "#00e676", True), ("B", "5 m/s", "#94a3b8", False), ("C", "25 m/s", "#94a3b8", False), ("D", "7 m/s", "#94a3b8", False)]
    for i, (letter, text, col, is_correct) in enumerate(choices):
        cx = 130 + (i % 2) * 550
        cy = 380 + (i // 2) * 75
        fill_box = (0, 230, 118, 30) if is_correct else (15, 30, 50, 200)
        draw.rounded_rectangle((cx, cy, cx + 510, cy + 60), radius=12, fill=fill_box, outline=col, width=2)
        draw.text((cx + 20, cy + 16), f"{letter}.  {text}", font=get_font(24, is_correct), fill=col)
        
    # Question Card 2 (Summary)
    draw.rounded_rectangle((100, 590, 1260, 840), radius=22, fill=(10, 24, 45, 240), outline=(40, 80, 120, 255), width=2)
    draw.text((130, 620), "Q2: How far does it travel in those 5 seconds? (x = v₀t + ½at²)", font=get_font(28, True), fill="white")
    draw.rounded_rectangle((130, 680, 640, 740), radius=12, fill=(0, 230, 118, 30), outline="#00e676", width=2)
    draw.text((150, 696), "Answer: 25 m  (Calculated & Verified ✓)", font=get_font(24, True), fill="#00e676")
    draw.text((130, 770), "Explanation: x = 0 + 0.5(2)(5²) = 25 m. Direct substitution with SI units.", font=get_font(22), fill="#94a3b8")
    
    # Score Summary Widget on Right
    draw.rounded_rectangle((1300, 280, 1820, 840), radius=26, fill=(5, 15, 30, 250), outline=(0, 230, 118, 220), width=3)
    draw.text((1440, 340), "QUIZ SCORE", font=get_font(30, True), fill="#a5c4e8")
    draw.text((1420, 410), "100%", font=get_font(110, True), fill="#00e676")
    draw.text((1420, 550), "3 of 3 Correct", font=get_font(32, True), fill="white")
    draw.text((1340, 630), "• Instant automated grading\n• Full step-by-step explanations\n• Saved to student learning history", font=get_font(24), fill="#94a3b8")
    
    draw.rounded_rectangle((1340, 740, 1780, 805), radius=14, fill=(0, 230, 118, 240))
    draw.text((1430, 758), "Mastery Achieved", font=get_font(26, True), fill="#051423")
    
    return img

def make_admin_slide() -> Image.Image:
    img = create_gradient_canvas()
    draw = ImageDraw.Draw(img, "RGBA")
    
    draw.rounded_rectangle((100, 60, 480, 115), radius=14, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    draw.text((120, 75), "STAGE 5 · ADMIN & TELEMETRY", font=get_font(24, True), fill="#35d9ff")
    
    draw.text((100, 140), "Curriculum Publishing & AI Audit Queue", font=get_font(54, True), fill="white")
    draw.text((100, 215), "Live at https://aitutor-admin.mekhla.digital", font=get_font(30), fill="#a5c4e8")
    
    # 3 Stat Cards
    stats = [
        ("31 Topics", "MoEYS Curriculum Authored", "#35d9ff"),
        ("100% Real-Time", "Tutor Gate Synchronization", "#00e676"),
        ("Audit Queue", "Human-in-the-Loop AI Review", "#ffab00")
    ]
    for i, (big, label, col) in enumerate(stats):
        x = 100 + i * 590
        draw.rounded_rectangle((x, 280, x + 550, 450), radius=20, fill=(10, 24, 45, 240), outline=(40, 80, 120, 255), width=2)
        draw.text((x + 40, 315), big, font=get_font(56, True), fill=col)
        draw.text((x + 40, 395), label, font=get_font(24), fill="#c5d8f2")
        
    # Feature Box
    draw.rounded_rectangle((100, 480, 1820, 850), radius=24, fill=(5, 14, 28, 230), outline=(30, 60, 95, 255), width=3)
    features = [
        "Curriculum Versioning: Draft, Review, and Publish stages with immutable chunk ID tracking.",
        "Deterministic Formula Editor: Authors KaTeX equations, parameter definitions, and Khmer terms.",
        "Live Telemetry & Verification: Monitors client board action lifecycle, animation latencies, and drops.",
        "Audit Trail: Every AI generation and human review is permanently stamped for pedagogical quality."
    ]
    y = 525
    for idx, f in enumerate(features, 1):
        draw.ellipse((140, y + 8, 172, y + 40), fill=(53, 217, 255, 40), outline="#35d9ff", width=2)
        draw.text((150, y + 10), str(idx), font=get_font(20, True), fill="#35d9ff")
        draw.text((195, y), f, font=get_font(28), fill="#e2e8f0")
        y += 75
        
    return img

def main():
    out_dir = ROOT / "full_flow_slides"
    out_dir.mkdir(exist_ok=True)
    
    shots_dir = ROOT.parent / "ai_tutor" / "build" / "demo_shots"
    
    # Slide 1: Intro Title Card
    s1 = create_gradient_canvas()
    d1 = ImageDraw.Draw(s1)
    d1.rounded_rectangle((100, 100, 520, 160), radius=16, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    d1.text((125, 115), "KIRIROM INSTITUTE OF TECHNOLOGY", font=get_font(24, True), fill="#35d9ff")
    d1.text((100, 240), "Rean AI (រៀន AI)", font=get_font(90, True), fill="white")
    d1.text((100, 360), "Cambodia Grade 10-12 High School STEM AI Visual Tutor", font=get_font(38), fill="#9fc2ea")
    d1.rounded_rectangle((100, 480, 1820, 780), radius=28, fill=(5, 14, 28, 230), outline=(53, 217, 255, 200), width=3)
    d1.text((150, 530), "• The AI tutor that teaches on a whiteboard — not another chatbot", font=get_font(36, True), fill="#ffffff")
    d1.text((150, 600), "• Verified by SymPy & deterministic solvers — zero mathematical hallucination", font=get_font(36, True), fill="#ffffff")
    d1.text((150, 670), "• Full bilingual support (English + Khmer) across Mathematics, Physics, & Chemistry", font=get_font(36, True), fill="#ffffff")
    d1.text((100, 840), "LIVE PRODUCT DEMO · OCT 2026", font=get_font(34, True), fill="#35d9ff")
    d1.text((100, 900), "https://aitutor.mekhla.digital", font=get_font(30), fill="#a5c4e8")
    s1.convert("RGB").save(out_dir / "01_intro.png", quality=95)
    
    # Slide 2: Lesson Reader & Concepts
    s2 = make_title_slide(
        "STAGE 1: LESSON READER",
        "Curriculum Concept & KaTeX Formula Reader",
        "Students review definitions, formulas, and common misconceptions before practicing.",
        [
            "Structured Pedagogy: Explains topic fundamentals in clear Khmer and English.",
            "KaTeX Formulas: Clean mathematical notation with explicit variable definitions.",
            "Common Misconceptions: Proactively warns students of typical examination traps.",
            "1-Click 'Watch on Whiteboard': Instantly launches the animated teacher solution."
        ]
    )
    s2.convert("RGB").save(out_dir / "02_lesson_reader.png", quality=95)
    
    # Slide 3: Live Whiteboard English (Limits)
    s3 = compose_board_showcase(
        "2A",
        "Animated Whiteboard: Grade 12 Limits (English)",
        "Step-by-step rational limit resolution with LaTeX reveal clipping.",
        shots_dir / "01-limits-english.png"
    )
    s3.convert("RGB").save(out_dir / "03_whiteboard_en.png", quality=95)
    
    # Slide 4: Live Whiteboard Khmer (Limits)
    s4 = compose_board_showcase(
        "2B",
        "Animated Whiteboard: Grade 12 Limits (Khmer)",
        "Full pedagogical solution written natively in Khmer with Khmer numerals (០-៩).",
        shots_dir / "02-limits-khmer.png"
    )
    s4.convert("RGB").save(out_dir / "04_whiteboard_km.png", quality=95)
    
    # Slide 5: Physics Kinematics & Diagrams
    s5 = compose_board_showcase(
        "2C",
        "Multi-Subject Support: Physics Kinematics & Diagrams",
        "Newtonian mechanics and kinematic equations with explicit physical units.",
        shots_dir / "03-physics-free-body-diagram.png"
    )
    s5.convert("RGB").save(out_dir / "05_physics.png", quality=95)
    
    # Slide 6: Chemistry Stoichiometry
    s6 = compose_board_showcase(
        "2D",
        "Multi-Subject Support: Chemistry Stoichiometry",
        "Balanced chemical equations (2H₂ + O₂ → 2H₂O) and mole ratio conservation.",
        shots_dir / "04-chemistry-reaction.png"
    )
    s6.convert("RGB").save(out_dir / "06_chemistry.png", quality=95)
    
    # Slide 7: Step-level Follow-up Q&A
    s7 = make_title_slide(
        "STAGE 3: STEP-LEVEL Q&A",
        "Interactive Step Clarification Without Rebuilding",
        "Students can pause at any step and ask specific questions about the deduction.",
        [
            "Contextual Grounding: The AI knows exactly which equation step the student is viewing.",
            "Single-Write Guarantee: The board never replays from scratch during Q&A.",
            "Bilingual Redirect: Redirects off-topic queries gracefully back to the current topic.",
            "Anti-Leak Sanitizer: Protects subsequent step solutions until the student advances."
        ]
    )
    s7.convert("RGB").save(out_dir / "07_followup_qa.png", quality=95)
    
    # Slide 8: Targeted Practice Quiz
    s8 = make_quiz_slide()
    s8.convert("RGB").save(out_dir / "08_practice_quiz.png", quality=95)
    
    # Slide 9: Admin Dashboard & Telemetry
    s9 = make_admin_slide()
    s9.convert("RGB").save(out_dir / "09_admin_dashboard.png", quality=95)
    
    # Slide 10: Outro Slide
    s10 = create_gradient_canvas()
    d10 = ImageDraw.Draw(s10)
    d10.text((960, 400), "REAN AI (រៀន AI)", font=get_font(88, True), fill="#35d9ff", anchor="mm")
    d10.text((960, 500), "Verified Visual Tutoring for Cambodian High School STEM", font=get_font(42), fill="white", anchor="mm")
    d10.text((960, 580), "Live on Production: https://aitutor.mekhla.digital", font=get_font(34), fill="#a5c4e8", anchor="mm")
    d10.text((960, 640), "Admin Studio: https://aitutor-admin.mekhla.digital", font=get_font(34), fill="#a5c4e8", anchor="mm")
    d10.text((960, 750), "Thank You! Ready for Demonstration.", font=get_font(36, True), fill="#00e676", anchor="mm")
    s10.convert("RGB").save(out_dir / "10_outro.png", quality=95)
    
    print(f"Generated 10 full flow slides in {out_dir}")

if __name__ == "__main__":
    main()

import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SHOTS_DIR = ROOT.parent / "ai_tutor" / "build" / "demo_shots"
AUDIO_DIR = ROOT / "voiceover_audio"
AUDIO_DIR.mkdir(exist_ok=True)
SLIDES_DIR = ROOT / "voiceover_slides"
SLIDES_DIR.mkdir(exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"

def get_font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_PATH, size=size, index=(1 if bold else 0))

def create_base_canvas():
    canvas = Image.new("RGBA", (1920, 1080), "#07111f")
    draw = ImageDraw.Draw(canvas, "RGBA")
    for y in range(1080):
        blend = y / 1079
        draw.line((0, y, 1920, y), fill=(7, round(17 + 16 * blend), round(31 + 35 * blend), 255))
    return canvas

def make_slide_with_image(badge_text: str, title: str, subtitle: str, image_path: Path | None, bullets: list[str] | None = None) -> Image.Image:
    canvas = create_base_canvas()
    draw = ImageDraw.Draw(canvas, "RGBA")
    
    # Top pill
    draw.rounded_rectangle((80, 50, 520, 105), radius=14, fill=(15, 35, 60, 220), outline=(53, 217, 255, 200), width=2)
    draw.text((100, 65), badge_text.upper(), font=get_font(24, True), fill="#35d9ff")
    
    draw.text((80, 125), title, font=get_font(52, True), fill="white")
    draw.text((80, 195), subtitle, font=get_font(28), fill="#9fc2ea")
    
    if image_path and image_path.exists():
        raw = Image.open(image_path).convert("RGBA")
        target_w, target_h = 1760, 780
        scale = min(target_w / raw.width, target_h / raw.height)
        sw, sh = round(raw.width * scale), round(raw.height * scale)
        resized = raw.resize((sw, sh), Image.Resampling.LANCZOS)
        
        px = 80 + (target_w - sw) // 2
        py = 250 + (target_h - sh) // 2
        
        draw.rounded_rectangle((px - 6, py - 6, px + sw + 6, py + sh + 6), radius=18, fill=(3, 8, 16, 255), outline=(53, 217, 255, 180), width=3)
        canvas.alpha_composite(resized, (px, py))
    elif bullets:
        draw.rounded_rectangle((80, 260, 1840, 960), radius=28, fill=(5, 14, 28, 230), outline=(30, 60, 95, 255), width=3)
        y = 330
        for i, b in enumerate(bullets, 1):
            draw.ellipse((130, y + 10, 168, y + 48), fill=(53, 217, 255, 40), outline="#35d9ff", width=2)
            draw.text((142, y + 12), str(i), font=get_font(24, True), fill="#35d9ff")
            parts = b.split(":", 1)
            if len(parts) == 2:
                draw.text((190, y), parts[0] + ":", font=get_font(34, True), fill="#ffffff")
                box = draw.textbbox((0, 0), parts[0] + ": ", font=get_font(34, True))
                draw.text((190 + (box[2] - box[0]), y), parts[1], font=get_font(34), fill="#c5d8f2")
            else:
                draw.text((190, y), b, font=get_font(34), fill="#c5d8f2")
            y += 120

    return canvas

# Segments definition
SEGMENTS = [
    {
        "id": "01_intro",
        "badge": "Rean AI · Closing Project",
        "title": "Rean AI (រៀន AI) · High School AI Visual Tutor",
        "subtitle": "Cambodia MoEYS Grade 10–12 STEM Visual Whiteboard Platform",
        "type": "bullets",
        "bullets": [
            "Whiteboard-First Pedagogy: Teaches step-by-step like a teacher at the board, not a chatbot.",
            "Deterministic Grounding: All calculations verified by SymPy and domain solvers — zero math hallucinations.",
            "Bilingual Excellence: Native Khmer typography, numerals, and speech with English parity.",
            "Live Production Deployment: Student App and Admin Studio live at aitutor.mekhla.digital."
        ],
        "speech": "Welcome to Rean AI, the intelligent visual tutor designed specifically for Cambodia's Grade 10 to 12 STEM curriculum. It is an AI tutor that teaches on an animated whiteboard, not another generic text chatbot."
    },
    {
        "id": "02_curriculum",
        "badge": "Stage 1 · Guided Curriculum",
        "title": "Interactive Lesson Reader & KaTeX Formulas",
        "subtitle": "Clear concepts, formula cheat sheets, and common exam misconceptions",
        "type": "bullets",
        "bullets": [
            "Structured Syllabus: 31 published topics across Grades 10, 11, and 12 in Math, Physics, and Chemistry.",
            "Mathematical Precision: Clean KaTeX formula cards with parameter definitions and boundary conditions.",
            "Misconception Alerts: Highlights frequent high school exam traps before students begin practice.",
            "One-Click Demonstration: Launches the animated worked solution directly onto the whiteboard."
        ],
        "speech": "Students begin in the curriculum catalog. Here, they access structured lesson readers featuring KaTeX formulas, fundamental definitions, and common examination misconceptions."
    },
    {
        "id": "03_whiteboard_en",
        "badge": "Stage 2A · Whiteboard Engine (English)",
        "title": "Step-by-Step Whiteboard: Grade 12 Limits",
        "subtitle": "Evaluating rational limits with 0/0 indeterminate forms and LaTeX clipping",
        "type": "image",
        "image": SHOTS_DIR / "01-limits-english.png",
        "speech": "With one tap on 'Watch on Whiteboard', the tutor animates the full worked solution line by line. Every equation is verified by SymPy, clipping LaTeX smoothly without arithmetic hallucinations."
    },
    {
        "id": "04_whiteboard_km",
        "badge": "Stage 2B · Native Khmer Depth",
        "title": "Bilingual Whiteboard: Grade 12 Limits (Khmer)",
        "subtitle": "Native Khmer mathematical deduction with Khmer numerals (០–៩)",
        "type": "image",
        "image": SHOTS_DIR / "02-limits-khmer.png",
        "speech": "Rean AI delivers native Khmer typography and numerals. Problem statements and deductions are explained with natural Khmer voiceover and mathematical terms."
    },
    {
        "id": "05_physics_diagram",
        "badge": "Stage 2C · Physics Kinematics & Mechanics",
        "title": "Multi-Subject STEM: Physics Free Body Diagrams",
        "subtitle": "Constant acceleration equations (v = u + at, s = ut + ½at²) with explicit SI units",
        "type": "image",
        "image": SHOTS_DIR / "03-physics-free-body-diagram.png",
        "speech": "Beyond mathematics, Rean AI powers Grade 12 physics kinematics with free body diagrams, and chemistry stoichiometry with balanced reactions and mole ratios."
    },
    {
        "id": "06_followup_qa",
        "badge": "Stage 3 · Step-Level Q&A",
        "title": "Interactive Step Follow-Up Without Replaying",
        "subtitle": "Single-write board state serial prevents erasing or redrawing previous steps",
        "type": "bullets",
        "bullets": [
            "Context-Aware Follow-Up: The tutor understands the specific step and equation under discussion.",
            "Single-Write Invariant: ValueKey serial identity keeps the board intact during follow-up questions.",
            "Bilingual Redirection: Politely guides off-topic prompts back to the core lesson curriculum.",
            "Answer Lock Protection: Prevents premature answer revelation until prerequisite understanding is reached."
        ],
        "speech": "Students can pause at any step and ask: 'Why did we factor here?' The tutor clarifies that exact equation without redrawing or replaying the board."
    },
    {
        "id": "07_practice_quiz",
        "badge": "Stage 4 · Practice Quiz Loop",
        "title": "Targeted Practice Quizzes with Instant Scoring",
        "subtitle": "3-question practice loop with immediate feedback, green correct states, and explanations",
        "type": "bullets",
        "bullets": [
            "Targeted Question Selection: Automatically serves problems tailored to the lesson's learning signals.",
            "Interactive Multiple Choice & Numeric: Clean student-friendly options with LaTeX math notation.",
            "Instant Automated Grading: Evaluates answer equivalency and awards immediate scores.",
            "Pedagogical Feedback: Every question provides step-by-step correction to reinforce learning."
        ],
        "speech": "To reinforce mastery, students take a targeted practice quiz. Three problems are dynamically scored, offering immediate feedback and step-by-step explanations."
    },
    {
        "id": "08_admin_studio",
        "badge": "Stage 5 · Admin Studio & Telemetry",
        "title": "Next.js Curriculum Management & AI Audit Queue",
        "subtitle": "31 MoEYS topics authored with real-time telemetry and human review",
        "type": "bullets",
        "bullets": [
            "Curriculum Authoring: Teachers publish structured lessons directly to the AI Tutor's curriculum gate.",
            "Human-in-the-Loop Review: Logs student interactions for continuous pedagogical auditing.",
            "Client Telemetry: Tracks board animation rendering latency, frame rates, and completion stats.",
            "Production URL: Deployed and managing sessions live at aitutor-admin.mekhla.digital."
        ],
        "speech": "For teachers and administrators, the Next.js portal manages 31 published curriculum topics and monitors live student telemetry and AI audit queues."
    },
    {
        "id": "09_outro",
        "badge": "Closing · Live on Production",
        "title": "Rean AI: Transforming STEM Learning in Cambodia",
        "subtitle": "Team 4 · Kirirom Institute of Technology · October 2026",
        "type": "bullets",
        "bullets": [
            "Live Student App: https://aitutor.mekhla.digital",
            "Live Admin Portal: https://aitutor-admin.mekhla.digital",
            "Phase I Fully Delivered: Whiteboard Engine, Multi-Subject Solvers, Lesson Reader, Practice Quizzes.",
            "Phase II Ready: Supervised classroom pilot at Cambodian high schools."
        ],
        "speech": "Rean AI transforms passive screen time into active visual understanding. Live today on production at aitutor dot mekhla dot digital."
    }
]

def get_audio_duration(file_path: Path) -> float:
    cmd = ["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())

def main():
    print("--- 1. Generating Speech Audio & Measuring Durations ---")
    segment_durations = []
    audio_files = []
    
    for seg in SEGMENTS:
        seg_id = seg["id"]
        aiff_path = AUDIO_DIR / f"{seg_id}.aiff"
        wav_path = AUDIO_DIR / f"{seg_id}.wav"
        
        # macOS TTS
        subprocess.run(["say", "-v", "Daniel", "-r", "165", "-o", str(aiff_path), seg["speech"]], check=True)
        # Convert to WAV with 0.5s padding
        subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", str(aiff_path), "-af", "apad=pad_dur=0.5", str(wav_path)], check=True, capture_output=True)
        
        dur = get_audio_duration(wav_path)
        segment_durations.append(dur)
        audio_files.append(wav_path)
        print(f"Segment {seg_id}: {dur:.2f}s")
        
    print(f"Total Audio Duration: {sum(segment_durations):.2f}s")
    
    print("\n--- 2. Generating High-Resolution 1080p Visual Slides ---")
    slide_images = []
    for seg in SEGMENTS:
        seg_id = seg["id"]
        png_path = SLIDES_DIR / f"{seg_id}.png"
        img_path = seg.get("image")
        bullets = seg.get("bullets")
        
        slide = make_slide_with_image(seg["badge"], seg["title"], seg["subtitle"], img_path, bullets)
        slide.convert("RGB").save(png_path, quality=95)
        slide_images.append(png_path)
        print(f"Saved slide {png_path.name}")
        
    print("\n--- 3. Merging Segments into Full Video with Synchronized Voiceover ---")
    
    # Render individual video clips for each segment
    clip_files = []
    for i, seg in enumerate(SEGMENTS):
        seg_id = seg["id"]
        png_path = slide_images[i]
        wav_path = audio_files[i]
        dur = segment_durations[i]
        clip_path = ROOT / f"clip_{seg_id}.mp4"
        
        # Create clip with exact duration matching speech
        cmd = [
            "/opt/homebrew/bin/ffmpeg", "-y",
            "-loop", "1", "-i", str(png_path),
            "-i", str(wav_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(dur),
            str(clip_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        clip_files.append(clip_path)
        print(f"Rendered segment clip {clip_path.name} ({dur:.2f}s)")
        
    # Concatenate all clips
    concat_list = ROOT / "clips_list.txt"
    with open(concat_list, "w") as f:
        for c in clip_files:
            f.write(f"file '{c.resolve()}'\n")
            
    final_video = ROOT / "rean-ai-master-voiceover-demo.mp4"
    cmd_concat = [
        "/opt/homebrew/bin/ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(final_video)
    ]
    subprocess.run(cmd_concat, check=True, capture_output=True)
    print(f"\n Master Demo Video Successfully Created: {final_video}")
    
    # Clean up intermediate clips
    for c in clip_files:
        c.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)

if __name__ == "__main__":
    main()

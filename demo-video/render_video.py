import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLIDES_DIR = ROOT / "full_flow_slides"
OUTPUT_VIDEO = ROOT / "rean-ai-full-flow-presentation.mp4"

# Each slide shown for 4.5 seconds with 0.5s fade
slides = sorted(list(SLIDES_DIR.glob("*.png")))
print(f"Found {len(slides)} slides.")

# Create an input list for ffmpeg concat
concat_file = ROOT / "slides_list.txt"
with open(concat_file, "w") as f:
    for s in slides:
        f.write(f"file '{s.resolve()}'\n")
        f.write("duration 4.5\n")
    # Repeat last image once without duration for concat demuxer
    if slides:
        f.write(f"file '{slides[-1].resolve()}'\n")

cmd = [
    "/opt/homebrew/bin/ffmpeg",
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", str(concat_file),
    "-vf", "scale=1920:1080,format=yuv420p",
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "18",
    "-r", "25",
    str(OUTPUT_VIDEO)
]

print("Running ffmpeg...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print(f"Successfully generated {OUTPUT_VIDEO}")
else:
    print("FFmpeg error:", res.stderr)

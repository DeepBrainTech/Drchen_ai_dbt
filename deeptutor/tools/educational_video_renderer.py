import subprocess
import textwrap
from pathlib import Path


def run_ffmpeg(args, cwd):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-nostdin", "-y", *args],
        cwd=str(cwd),
        capture_output=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace")[-1500:]
        )


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def render_educational_video(scenes, output_dir):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    clips = []

    for index, scene in enumerate(scenes):
        prefix = f"scene_{index:03d}"
        audio = output_dir / f"{prefix}.mp3"
        audio.write_bytes(scene["audio"])

        duration = audio_duration(audio)

        title = textwrap.fill(scene["title"], width=35)
        content = textwrap.fill(scene["content"], width=46)

        (output_dir / f"{prefix}_title.txt").write_text(
            title, encoding="utf-8"
        )
        (output_dir / f"{prefix}_content.txt").write_text(
            content, encoding="utf-8"
        )

        narration = scene.get("narration", scene["content"])
        words = narration.split()
        chunks = [
            " ".join(words[i:i + 8])
            for i in range(0, len(words), 8)
        ]

        subtitle_filters = []
        elapsed = 0.0

        for number, chunk in enumerate(chunks):
            end = elapsed + duration * len(chunk.split()) / max(len(words), 1)

            subtitle_file = f"{prefix}_sub_{number:03d}.txt"
            (output_dir / subtitle_file).write_text(
                textwrap.fill(chunk, width=48),
                encoding="utf-8",
            )

            subtitle_filters.append(
                f"drawtext=textfile={subtitle_file}:"
                "expansion=none:fontsize=30:fontcolor=white:"
                "box=1:boxcolor=black@0.85:boxborderw=14:"
                "x=(w-tw)/2:y=h-th-65:"
                f"enable='between(t,{elapsed:.3f},{end:.3f})'"
            )

            elapsed = end

        filters = (
            "drawbox=x=0:y=0:w=iw:h=12:color=0x38BDF8:t=fill,"
            "drawbox=x=70:y=80:w=1140:h=420:"
            "color=0x172B46:t=fill,"
            f"drawtext=textfile={prefix}_title.txt:"
            "expansion=none:fontsize=42:fontcolor=0x38BDF8:"
            "x=(w-tw)/2:y=120,"
            f"drawtext=textfile={prefix}_content.txt:"
            "expansion=none:fontsize=32:fontcolor=white:"
            "x=(w-tw)/2:y=260:line_spacing=12,"
            "fade=t=in:st=0:d=0.5"
        )

        if subtitle_filters:
            filters += "," + ",".join(subtitle_filters)

        clip = f"{prefix}.mp4"

        run_ffmpeg([
            "-f", "lavfi",
            "-i", "color=c=0x0B172A:s=1280x720:r=25",
            "-i", audio.name,
            "-vf", filters,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-shortest", clip,
        ], output_dir)

        clips.append(clip)

    if not clips:
        raise ValueError("No video scenes provided.")

    manifest = output_dir / "scenes.txt"
    manifest.write_text(
        "\n".join(f"file '{clip}'" for clip in clips),
        encoding="utf-8",
    )

    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", manifest.name,
        "-c", "copy",
        "-movflags", "+faststart",
        "educational-video.mp4",
    ], output_dir)

    return output_dir / "educational-video.mp4"

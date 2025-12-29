from pathlib import Path
import sys

from mysite.universe.services.tts_service import get_tts_service


def main() -> int:
    text = (
        "Mars Control, this is STELLAR HORIZON requesting permission to circularize "
        "at 200 km altitude."
    )
    voices = [
        "pilot_M_0001",
        "pilot_M_0002",
        "pilot_F_0001",
        "controller_M_0001",
    ]

    service = get_tts_service()
    outdir = Path("audio/voices/generated")
    outdir.mkdir(parents=True, exist_ok=True)

    any_failed = False
    for v in voices:
        try:
            wav_bytes = service.generate(text=text, voice_id=v)
            out_path = outdir / f"{v}_sample.wav"
            out_path.write_bytes(wav_bytes)
            print(f"Generated {out_path} ({len(wav_bytes)} bytes)")
        except Exception as e:
            any_failed = True
            print(f"Failed for {v}: {e}")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())


import json
import sys
from pathlib import Path

from resume_generator import generate_resume_latex, compile_latex_to_pdf


def main() -> int:
    profile_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resume_profile.sample.json")
    output_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("resume.pdf")

    if not profile_path.exists():
        print(f"Profile JSON not found: {profile_path}")
        print("Usage: python3 build_resume.py <profile.json> [output.pdf]")
        return 1

    with profile_path.open("r", encoding="utf-8") as f:
        profile = json.load(f)

    latex_code = generate_resume_latex(profile)
    ok, result = compile_latex_to_pdf(latex_code, str(output_pdf))
    if not ok:
        print(f"Failed to compile PDF: {result}")
        return 1

    print(f"Resume generated: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

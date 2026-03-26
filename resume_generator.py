import os
import subprocess
import re
import shutil
from pathlib import Path
from jinja2 import Template


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = BASE_DIR / "templates" / "resume_template.tex.j2"


def _escape_latex(value: str) -> str:
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\~{}",
        "^": r"\^{}",
    }
    escaped = "".join(replacements.get(ch, ch) for ch in text)
    escaped = re.sub(r"\s+", " ", escaped).strip()
    return escaped


def _sanitize_profile(user_profile: dict) -> dict:
    cleaned = dict(user_profile or {})
    github_user = str(cleaned.get("github_user", "")).strip()
    linkedin_user = str(cleaned.get("linkedin_user", "")).strip()
    if not cleaned.get("github_url") and github_user:
        cleaned["github_url"] = f"https://github.com/{github_user}"
    if not cleaned.get("linkedin_url") and linkedin_user:
        cleaned["linkedin_url"] = f"https://linkedin.com/in/{linkedin_user}"

    scalar_fields = ["name", "email", "phone", "location", "summary", "github_url", "linkedin_url", "portfolio_url"]
    for key in scalar_fields:
        cleaned[key] = _escape_latex(cleaned.get(key, ""))

    cleaned["experience"] = cleaned.get("experience", [])
    cleaned["projects"] = cleaned.get("projects", [])
    cleaned["education"] = cleaned.get("education", [])
    cleaned["skills"] = cleaned.get("skills", [])
    cleaned["leadership"] = cleaned.get("leadership", [])
    cleaned["achievements"] = cleaned.get("achievements", [])

    for job in cleaned["experience"]:
        job["title"] = _escape_latex(job.get("title", ""))
        job["company"] = _escape_latex(job.get("company", ""))
        job["location"] = _escape_latex(job.get("location", ""))
        job["dates"] = _escape_latex(job.get("dates", ""))
        job["points"] = [_escape_latex(point) for point in job.get("points", [])]

    for project in cleaned["projects"]:
        project["name"] = _escape_latex(project.get("name", ""))
        project["tech"] = _escape_latex(project.get("tech", ""))
        project["description"] = _escape_latex(project.get("description", ""))
        project["url"] = project.get("url", "").strip()

    for edu in cleaned["education"]:
        edu["dates"] = _escape_latex(edu.get("dates", ""))
        edu["degree"] = _escape_latex(edu.get("degree", ""))
        edu["institution"] = _escape_latex(edu.get("institution", ""))
        edu["location"] = _escape_latex(edu.get("location", ""))

    for skill in cleaned["skills"]:
        skill["category"] = _escape_latex(skill.get("category", ""))
        skill["items"] = _escape_latex(skill.get("items", ""))

    for item in cleaned["leadership"]:
        item["role"] = _escape_latex(item.get("role", ""))
        item["org"] = _escape_latex(item.get("org", ""))
        item["location"] = _escape_latex(item.get("location", ""))
        item["dates"] = _escape_latex(item.get("dates", ""))
        item["points"] = [_escape_latex(point) for point in item.get("points", [])]

    cleaned["achievements"] = [_escape_latex(item) for item in cleaned["achievements"]]
    return cleaned

def generate_resume_latex(user_profile: dict) -> str:
    """
    Generates LaTeX for a resume using a file-based Jinja2 template.
    """
    if DEFAULT_TEMPLATE_PATH.exists():
        latex_template = DEFAULT_TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"Template not found: {DEFAULT_TEMPLATE_PATH}")

    template = Template(latex_template)
    safe_profile = _sanitize_profile(user_profile)
    return template.render(**safe_profile)

def compile_latex_to_pdf(latex_code: str, output_path: str = "output.pdf"):
    """
    Writes the LaTeX string to a file and compiles via pdflatex.
    """
    with open("temp.tex", "w", encoding="utf-8") as f:
        f.write(latex_code)
    try:
        pdflatex_bin = shutil.which("pdflatex")
        if not pdflatex_bin and Path("/Library/TeX/texbin/pdflatex").exists():
            pdflatex_bin = "/Library/TeX/texbin/pdflatex"
        if not pdflatex_bin:
            return False, "pdflatex not installed on server."

        # Check if pdflatex is installed
        subprocess.run([pdflatex_bin, "-version"], check=True, capture_output=True)
        compile_proc = subprocess.run(
            [pdflatex_bin, "-interaction=nonstopmode", "temp.tex"],
            check=True,
            capture_output=True,
            text=True,
        )
        if os.path.exists("temp.pdf"):
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename("temp.pdf", output_path)
            return True, output_path
        return False, "temp.pdf was not generated."
    except FileNotFoundError:
        return False, "pdflatex not installed on server."
    except subprocess.CalledProcessError as e:
        err_tail = (e.stderr or e.stdout or "")[-800:]
        return False, f"pdflatex compilation failed. Details: {err_tail}"
    except Exception as e:
        return False, str(e)
    finally:
        # Cleanup
        for ext in ['.tex', '.aux', '.log', '.out']:
            if os.path.exists(f"temp{ext}"):
                try:
                    os.remove(f"temp{ext}")
                except:
                    pass

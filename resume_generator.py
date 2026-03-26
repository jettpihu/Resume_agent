import os
import subprocess
from jinja2 import Template

def generate_resume_latex(user_profile: dict) -> str:
    """
    Uses Jinja2 to template a LaTeX resume using the user's provided template.
    """
    latex_template = r"""
\documentclass[a4paper,12pt]{article}

% PACKAGES
\usepackage{url}
\usepackage{parskip}
\RequirePackage{color}
\RequirePackage{graphicx}
\usepackage[usenames,dvipsnames]{xcolor}
\usepackage[scale=0.9]{geometry}
\usepackage{tabularx}
\usepackage{enumitem}
\newcolumntype{C}{>{\centering\arraybackslash}X}
\usepackage{titlesec}
\usepackage{hyperref}

\definecolor{linkcolour}{rgb}{0,0.2,0.6}
\hypersetup{colorlinks,breaklinks,urlcolor=linkcolour,linkcolour=linkcolour}

%for social icons
\usepackage{fontawesome5}

% job listing environments
\newenvironment{jobshort}[2]
    {
    \begin{tabularx}{\linewidth}{@{}l X r@{}}
    \textbf{#1} & \hfill & #2 \\[3.75pt]
    \end{tabularx}
    }
    {
    }

\newenvironment{joblong}[2]
    {
    \begin{tabularx}{\linewidth}{@{}l X r@{}}
    \textbf{#1} & \hfill & #2 \\[3.75pt]
    \end{tabularx}
    \begin{minipage}[t]{\linewidth}
    \begin{itemize}[nosep,after=\strut, leftmargin=1em, itemsep=3pt,label=--]
    }
    {
    \end{itemize}
    \end{minipage}
    }

\begin{document}
\pagestyle{empty}

% TITLE
\begin{tabularx}{\linewidth}{@{} C @{}}
\Huge{ {{ name }} } \\[7.5pt]
\href{https://github.com/{{ github_user }}}{\raisebox{-0.05\height}\faGithub\ github.com/{{ github_user }} } \ $|$ \
\href{https://www.linkedin.com/in/{{ linkedin_user }} }{\raisebox{-0.05\height}\faLinkedin\ linkedin.com/in/{{ linkedin_user }} } \ $|$ \
\href{mailto: {{ email }} }{\raisebox{-0.05\height}\faEnvelope\ {{ email }} } \ $|$ \
{{ location }} \\
\end{tabularx}

% SUMMARY
\section{Summary}
{{ summary }}

% EXPERIENCE
\section{Experience}
{% for job in experience %}
\begin{joblong}{ {{ job.title }} }{ {{ job.dates }} }
{% for point in job.points %}
\item {{ point }}
{% endfor %}
\end{joblong}
{% endfor %}

% PROJECTS
\section{Projects}
{% for project in projects %}
\begin{tabularx}{\linewidth}{ @{}l r@{} }
\textbf{ {{ project.name }} } & \hfill \href{ {{ project.url }} }{GitHub} \\[3.75pt]
\multicolumn{2}{@{}X@{}}{ {{ project.description }} } \\
\end{tabularx}
{% endfor %}

% EDUCATION
\section{Education}
{% for edu in education %}
\begin{tabularx}{\linewidth}{@{}l X@{}}
{{ edu.dates }} & {{ edu.degree }} \\
 & \textbf{ {{ edu.institution }} }, {{ edu.location }} \\
\end{tabularx}
{% endfor %}

% SKILLS
\section{Skills}
\begin{tabularx}{\linewidth}{@{}l X@{}}
{% for skill_cat in skills %}
\textbf{ {{ skill_cat.category }} } & {{ skill_cat.items }} \\
{% endfor %}
\end{tabularx}

\vfill
\center{\footnotesize Last updated: \today}

\end{document}
"""
    template = Template(latex_template)
    return template.render(**user_profile)

def compile_latex_to_pdf(latex_code: str, output_path: str = "output.pdf"):
    """
    Writes the LaTeX string to a file and compiles via pdflatex.
    """
    with open("temp.tex", "w", encoding="utf-8") as f:
        f.write(latex_code)
    try:
        # Check if pdflatex is installed
        subprocess.run(["pdflatex", "-version"], check=True, capture_output=True)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "temp.tex"], check=True, capture_output=True)
        if os.path.exists("temp.pdf"):
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename("temp.pdf", output_path)
            return True, output_path
        return False, "temp.pdf was not generated."
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

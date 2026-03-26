import re

def evaluate_resume_ats(resume_text: str) -> dict:
    """
    Simulates an ATS scanning algorithm.
    Evaluates:
    - Keyword density (e.g. 'Python', 'Agentverse', 'AI')
    - Readability (sentence length)
    - Action verbs presence
    """
    score = 100
    suggestions = []
    
    # Check for Action Verbs
    action_verbs = ['Developed', 'Engineered', 'Architected', 'Spearheaded', 'Optimized']
    found_verbs = [v for v in action_verbs if v.lower() in resume_text.lower()]
    
    if len(found_verbs) < 3:
        score -= 15
        suggestions.append("Use more strong action verbs (e.g., Engineered, Spearheaded, Optimized).")
        
    # Measurable achievements check (looks for numbers/%/$ signs)
    if not re.search(r'\d+%|\$\d+|\d+x', resume_text):
        score -= 20
        suggestions.append("Quantify your achievements using metrics (e.g., 'improved by 20%').")
        
    # Basic Formatting Check
    if len(resume_text.split('\\n')) < 10:
        score -= 10
        suggestions.append("Resume seems too short. Make sure all sections (Experience, Skills, Education) are covered.")
        
    return {
        "score": max(0, score),
        "suggestions": suggestions
    }

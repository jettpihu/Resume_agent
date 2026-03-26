import os
import re
import json
import logging
import asyncio
import hashlib
import httpx
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

def _load_env_file() -> None:
    script_dir = Path(__file__).resolve().parent
    for base in (script_dir, Path.cwd()):
        env_file = base / ".env"
        if not env_file.is_file():
            continue
        try:
            with open(env_file, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if key and not os.environ.get(key):
                        os.environ[key] = value
        except OSError:
            pass
        break

_load_env_file()

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec
from uagents_core.contrib.protocols.payment import RequestPayment

# Core integration modules
from resume_generator import generate_resume_latex, compile_latex_to_pdf
from ats_checker import evaluate_resume_ats
from profile_fetcher import fetch_user_data
from payment_module import payment_proto, is_premium_user, FET_FUNDS

logging.basicConfig(level=logging.INFO)

AGENT_SEED_PHRASE = os.getenv("AGENT_SEED_PHRASE")
ADMIN_ADDR = os.getenv("ADMIN_ADDR")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")

agent = Agent(
    name="career_resume_agent",
    seed=AGENT_SEED_PHRASE,
    mailbox=True,
    port=8000,
)

# Reuse the secure helper logic
def strip_pii(text: str) -> str:
    safe = str(text)
    safe = re.sub(r'\b\d{4}\s?\d{4}\s?\d{4}\b', '[AADHAAR_REMOVED]', safe)
    safe = re.sub(r'\b[A-Za-z]{5}[0-9]{4}[A-Za-z]{1}\b', '[PAN_REMOVED]', safe)
    # Allows email/Github to pass but strips phone
    safe = re.sub(r'\b(?:\+?91|0)?[789]\d{9}\b', '[PHONE_REMOVED]', safe)
    return safe

async def call_asi_one(system_prompt: str, user_prompt: str) -> str:
    if not ASI_ONE_API_KEY:
        return "ASI_ONE_API_KEY missing. Mocked ATS generation response."
    headers = {"Authorization": f"Bearer {ASI_ONE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "asi1-mini", 
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], 
        "temperature": 0.2
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post("https://api.asi1.ai/v1/chat/completions", headers=headers, json=payload)
            return str(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        return f"Error: {e}"
    return "Error: Unknown execution failure."

resume_proto = Protocol(spec=chat_protocol_spec)

@resume_proto.on_message(ChatMessage)
async def handle_resume_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    
    user_text = "".join([str(getattr(item, "text", "")) for item in msg.content])
    safe_text = strip_pii(user_text)

    # SEC RULE 1: Kill Switch
    if "SHUTDOWN_ADMIN_2024" in safe_text:
        os._exit(0)

    # SEC RULE 2: GDPR & Privacy Consent
    if not ctx.storage.get(f"consent_{sender}"):
        if "AGREE" in safe_text.upper():
            ctx.storage.set(f"consent_{sender}", True)
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="Consent recorded. Send me your GitHub or LinkedIn ID, or paste your resume text! 🛡️")]))
        else:
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="🛡️ DPDPA/GDPR Compliance: Please reply with '**AGREE**' to process your resume data.")]))
        return

    # Trigger Payment Logic (Premium Feature: ATS Scoring / Unlimited)
    if "ATS SCORE" in safe_text.upper() and not is_premium_user(ctx, sender):
        response_text = "⚠️ **PREMIUM FEATURE:** To get an advanced ATS Score or unlock advanced templates, a micro-payment is required."
        await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text=response_text)]))
        await ctx.send(sender, RequestPayment(accepted_funds=[FET_FUNDS], recipient=str(agent.address), deadline_seconds=300, reference=str(uuid4()), description="Premium ATS Unlock (0.1 FET)", metadata={}))
        return

    # Intelligent Routing
    system_prompt = (
        "You are an AI Career Agent. Your task is to extract user information and route to the correct action.\n"
        "1. If the user provides a GitHub/LinkedIn URL, extract it and output: [ACTION: FETCH_PROFILE] <URL>\n"
        "2. If the user wants to generate a resume based on their data, you MUST output a valid JSON object starting with [ACTION: GENERATE_RESUME] followed by the JSON string. "
        "The JSON MUST follow this structure:\n"
        "{\n"
        "  \"name\": \"Full Name\", \"email\": \"Email\", \"github_user\": \"username\", \"linkedin_user\": \"username\", \"location\": \"City, Country\", \"summary\": \"Executive Summary\",\n"
        "  \"experience\": [{\"title\": \"Role\", \"dates\": \"Start - End\", \"points\": [\"Achievement 1\", \"Achievement 2\"]}],\n"
        "  \"projects\": [{\"name\": \"Project\", \"url\": \"link\", \"description\": \"Description\"}],\n"
        "  \"education\": [{\"dates\": \"Years\", \"degree\": \"Degree\", \"institution\": \"College\", \"location\": \"City\"}],\n"
        "  \"skills\": [{\"category\": \"Cat\", \"items\": \"Skill 1, Skill 2\"}]\n"
        "}\n"
        "3. If the user asks for an ATS score, output: [ACTION: SCORE_ATS] <Text content>"
    )
    
    response = await call_asi_one(system_prompt, safe_text)

    # Simulated integrations based on LLM output
    final_response = response
    
    if "[ACTION: FETCH_PROFILE]" in response:
        url_match = re.search(r'https?://\S+', response)
        url = url_match.group(0) if url_match else safe_text
        fetched_data = await fetch_user_data(url)
        final_response += f"\n\n*Fetched Profile Data:* {fetched_data}"
        
    if "[ACTION: SCORE_ATS]" in response:
        score_data = evaluate_resume_ats(safe_text)
        final_response += f"\n\n*ATS Score:* {score_data['score']}/100\n*Suggestions:* " + ", ".join(score_data['suggestions'])

    if "[ACTION: GENERATE_RESUME]" in response:
        try:
            json_str = response.split("[ACTION: GENERATE_RESUME]")[1].strip()
            # Clean up potential markdown formatting from LLM
            json_str = re.sub(r'^```json\s*|\s*```$', '', json_str, flags=re.MULTILINE)
            user_data = json.loads(json_str)
            
            # Generate LaTeX
            latex_code = generate_resume_latex(user_data)
            output_filename = f"resume_{user_data.get('name', 'user').replace(' ', '_')}.pdf"
            
            # Try to compile to PDF
            success, result = compile_latex_to_pdf(latex_code, output_filename)
            
            if success:
                final_response = f"✅ **Resume Generated Successfully!**\n\nI have created your professional PDF resume: `{output_filename}`.\nSince I am a local agent, you can find the file in my project folder on your computer! 📂"
            else:
                final_response = f"⚠️ **Resume Drafted (Wait for PDF)**\n\nI've generated the LaTeX structure for your resume, but I couldn't compile the PDF automatically (Error: {result}).\n\n**You can copy this LaTeX code into [Overleaf.com](https://www.overleaf.com) to get your PDF instantly:**\n\n```latex\n{latex_code}\n```"
        except Exception as e:
            final_response += f"\n\n❌ *Error during resume generation:* {e}"

    await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text=final_response)]))

@resume_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}")

agent.include(resume_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

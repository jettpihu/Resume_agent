import os
import re
import json
import logging
import asyncio
import httpx
import requests
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

# Core integration modules
from resume_generator import generate_resume_latex, compile_latex_to_pdf
from payment_module import (
    payment_proto,
    is_edit_unlocked,
    request_edit_payment_from_user,
    set_agent_wallet,
    set_on_payment_verified,
)

logging.basicConfig(level=logging.INFO)

AGENT_SEED_PHRASE = os.getenv("AGENT_SEED_PHRASE")
ADMIN_ADDR = os.getenv("ADMIN_ADDR")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
TMPFILES_API_URL = "https://tmpfiles.org/api/v1/upload"
EDIT_PREFIX = "EDIT RESUME:"

agent = Agent(
    name="career_resume_agent",
    seed=AGENT_SEED_PHRASE,
    mailbox=True,
    port=8001,
)
set_agent_wallet(agent.wallet)

# Reuse the secure helper logic
def strip_pii(text: str) -> str:
    safe = str(text)
    safe = re.sub(r'\b\d{4}\s?\d{4}\s?\d{4}\b', '[AADHAAR_REMOVED]', safe)
    safe = re.sub(r'\b[A-Za-z]{5}[0-9]{4}[A-Za-z]{1}\b', '[PAN_REMOVED]', safe)
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


async def _extract_profile_from_content(content_text: str) -> dict | None:
    system_prompt = (
        "You are an expert ATS resume writer and parser.\n"
        "Convert user-provided raw resume/career content into a strict JSON object.\n"
        "Return JSON only. Do not add markdown.\n"
        "Guidelines:\n"
        "- Keep bullets impact-first and ATS-friendly.\n"
        "- Use strong action verbs and measurable outcomes when present in user content.\n"
        "- Never invent companies, dates, or achievements.\n"
        "- Keep summary concise (2-3 lines).\n"
        "Schema:\n"
        "{\n"
        "  \"name\": \"Full Name\",\n"
        "  \"phone\": \"Phone\",\n"
        "  \"email\": \"Email\",\n"
        "  \"location\": \"City, Country\",\n"
        "  \"github_url\": \"https://github.com/username\",\n"
        "  \"linkedin_url\": \"https://linkedin.com/in/username\",\n"
        "  \"portfolio_url\": \"https://...\",\n"
        "  \"summary\": \"2-3 line summary\",\n"
        "  \"experience\": [{\"company\": \"Company\", \"location\": \"Location\", \"title\": \"Role\", \"dates\": \"Start - End\", \"points\": [\"Point\"]}],\n"
        "  \"projects\": [{\"name\": \"Project\", \"tech\": \"Tech stack\", \"url\": \"https://...\", \"description\": \"Description\"}],\n"
        "  \"education\": [{\"dates\": \"Years\", \"degree\": \"Degree\", \"institution\": \"College\", \"location\": \"City\"}],\n"
        "  \"skills\": [{\"category\": \"Category\", \"items\": \"Skill1, Skill2\"}],\n"
        "  \"leadership\": [{\"org\": \"Org\", \"location\": \"Location\", \"role\": \"Role\", \"dates\": \"Start - End\", \"points\": [\"Point\"]}],\n"
        "  \"achievements\": [\"Achievement\"]\n"
        "}\n"
        "If a field is unavailable, keep empty string or empty array."
    )
    response = await call_asi_one(system_prompt, content_text)
    return _extract_json_block(response)


async def _edit_profile_with_instructions(base_profile: dict, edit_instructions: str) -> dict | None:
    system_prompt = (
        "You are editing an existing ATS resume JSON.\n"
        "Apply user instructions to current JSON.\n"
        "Return JSON only with the exact same schema keys.\n"
        "Preserve all existing details unless user asks to modify/remove.\n"
        "Do not fabricate achievements or dates."
    )
    user_prompt = (
        f"Current JSON:\n{json.dumps(base_profile, ensure_ascii=False)}\n\n"
        f"Edit instructions:\n{edit_instructions}"
    )
    response = await call_asi_one(system_prompt, user_prompt)
    return _extract_json_block(response)


def _extract_json_block(text: str) -> dict | None:
    """
    Extracts the first JSON object found in free-form text.
    """
    if not text:
        return None
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            return None

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        return None


def upload_to_tmpfiles(file_bytes: bytes, filename: str = "resume.pdf") -> str:
    """
    Upload file bytes to tmpfiles.org and return direct download URL.
    """
    try:
        response = requests.post(
            TMPFILES_API_URL,
            files={"file": (filename, file_bytes, "application/pdf")},
            timeout=120,
        )
        response.raise_for_status()
        response_data = response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Tmpfiles upload failed: {e}") from e

    raw_url = response_data.get("data", {}).get("url")
    if not raw_url:
        raise RuntimeError(f"Tmpfiles upload returned no URL: {response_data}")

    # Convert listing page URL to direct download URL.
    return raw_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


async def _upload_pdf_to_temp_url(file_path: str) -> tuple[bool, str]:
    """
    Upload generated resume PDF to tmpfiles and return (success, url_or_error).
    """
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        temp_url = await asyncio.to_thread(upload_to_tmpfiles, pdf_bytes, Path(file_path).name)
        return True, temp_url
    except Exception as e:
        return False, f"Upload error: {e}"


def _profile_storage_key(sender: str) -> str:
    return f"resume_profile_{sender}"


def _pending_edit_key(sender: str) -> str:
    return f"pending_edit_{sender}"


def _looks_like_edit_intent(text: str) -> bool:
    normalized = (text or "").strip().lower()
    edit_keywords = [
        "edit",
        "change",
        "changes",
        "update",
        "modify",
        "revise",
        "improve",
        "fix",
    ]
    return any(word in normalized for word in edit_keywords)


def _looks_like_full_resume_content(text: str) -> bool:
    normalized = (text or "").lower()
    markers = ["experience", "education", "projects", "skills", "summary", "achievements"]
    marker_hits = sum(1 for marker in markers if marker in normalized)
    return len(normalized) > 800 or marker_hits >= 3


async def _generate_and_send_resume(ctx: Context, sender: str, user_profile: dict) -> None:
    ctx.logger.info("[resume-agent] action_generate_resume_started")
    latex_code = generate_resume_latex(user_profile)
    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", str(user_profile.get("name", "user"))).strip("_") or "user"
    output_filename = f"resume_{safe_name}.pdf"
    ctx.logger.info(f"[resume-agent] latex_generated output={output_filename}")

    success, result = compile_latex_to_pdf(latex_code, output_filename)
    if not success:
        ctx.logger.error(f"[resume-agent] pdf_compile_failed error={result}")
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=f"⚠️ Resume generation failed: {result}")],
            ),
        )
        return

    upload_ok, upload_data = await _upload_pdf_to_temp_url(output_filename)
    if not upload_ok:
        ctx.logger.error(f"[resume-agent] temp_upload_failed reason={upload_data}")
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=f"⚠️ PDF created but upload failed: {upload_data}")],
            ),
        )
        return

    ctx.storage.set(_profile_storage_key(sender), user_profile)
    ctx.logger.info(f"[resume-agent] temp_upload_success url={upload_data}")
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=f"✅ Resume ready.\nPDF link: {upload_data}")],
        ),
    )


async def _on_payment_verified(ctx: Context, sender: str) -> None:
    pending_edit = (ctx.storage.get(_pending_edit_key(sender)) or "").strip()
    if not pending_edit:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text="✅ Payment received. No pending edit was found.")],
            ),
        )
        return

    base_profile = ctx.storage.get(_profile_storage_key(sender)) or {}
    if not base_profile:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text="✅ Payment received, but no existing resume profile found. Please send full resume content first.")],
            ),
        )
        return

    ctx.logger.info("[resume-agent] payment_verified_auto_processing_pending_edit")
    edited_profile = await _edit_profile_with_instructions(base_profile, pending_edit)
    if not edited_profile:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text="Payment received, but edit processing failed. Please send your edit request again.")],
            ),
        )
        return

    ctx.storage.remove(_pending_edit_key(sender))
    await _generate_and_send_resume(ctx, sender, edited_profile)

resume_proto = Protocol(spec=chat_protocol_spec)

@resume_proto.on_message(ChatMessage)
async def handle_resume_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    
    user_text = "".join([str(getattr(item, "text", "")) for item in msg.content])
    safe_text = strip_pii(user_text)
    ctx.logger.info(f"[resume-agent] message_received sender={sender} chars={len(user_text)}")

    # SEC RULE 1: Kill Switch
    if "SHUTDOWN_ADMIN_2024" in safe_text:
        ctx.logger.warning("[resume-agent] kill_switch_triggered")
        os._exit(0)

    # SEC RULE 2: GDPR & Privacy Consent
    if not ctx.storage.get(f"consent_{sender}"):
        if "AGREE" in safe_text.upper():
            ctx.storage.set(f"consent_{sender}", True)
            ctx.logger.info(f"[resume-agent] consent_recorded sender={sender}")
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="Consent recorded. Please paste your resume content to generate your resume PDF.")]))
        else:
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="🛡️ DPDPA/GDPR Compliance: Please reply with '**AGREE**' to process your resume data.")]))
        return

    saved_profile = ctx.storage.get(_profile_storage_key(sender)) or {}
    pending_edit = ctx.storage.get(_pending_edit_key(sender))
    if pending_edit and is_edit_unlocked(ctx, sender):
        ctx.logger.info("[resume-agent] auto_applying_pending_edit")
        safe_text = f"{EDIT_PREFIX} {pending_edit}"
        user_text = safe_text
        ctx.storage.remove(_pending_edit_key(sender))

    implicit_edit = (
        bool(saved_profile)
        and not safe_text.upper().startswith(EDIT_PREFIX)
        and _looks_like_edit_intent(user_text)
        and not _looks_like_full_resume_content(user_text)
        and len(user_text.strip()) <= 500
    )
    if implicit_edit:
        ctx.logger.info("[resume-agent] implicit_edit_intent_detected")
        if len(user_text.strip()) < 15:
            await ctx.send(
                sender,
                ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[
                        TextContent(
                            type="text",
                            text="I can edit your last resume. Please send specific changes, e.g. 'EDIT RESUME: update summary and add Kubernetes in skills'.",
                        )
                    ],
                ),
            )
            return
        safe_text = f"{EDIT_PREFIX} {user_text}"
        user_text = safe_text

    if safe_text.upper().startswith(EDIT_PREFIX):
        if not is_edit_unlocked(ctx, sender):
            ctx.storage.set(_pending_edit_key(sender), user_text[len(EDIT_PREFIX):].strip())
            await ctx.send(
                sender,
                ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text="Resume editing requires a 0.01 FET payment. After payment, send any follow-up message and your pending edit will auto-apply.")],
                ),
            )
            await request_edit_payment_from_user(ctx, sender)
            return
        edit_instructions = user_text[len(EDIT_PREFIX):].strip()
        base_profile = saved_profile
        if not base_profile:
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="No existing resume found. Send your full resume content first.")]))
            return
        edited_profile = await _edit_profile_with_instructions(base_profile, edit_instructions)
        if not edited_profile:
            await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="Could not process edit instructions. Try again with clear changes.")]))
            return
        user_profile = edited_profile
    else:
        direct_json_payload = _extract_json_block(user_text)
        if isinstance(direct_json_payload, dict) and direct_json_payload.get("name"):
            ctx.logger.info("[resume-agent] direct_json_detected using_user_payload")
            user_profile = direct_json_payload
        else:
            ctx.logger.info("[resume-agent] parsing_profile_from_content")
            user_profile = await _extract_profile_from_content(user_text)
            if not user_profile:
                await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text="Could not parse resume content. Please send clear resume details (name, experience, projects, skills).")]))
                return

    try:
        await _generate_and_send_resume(ctx, sender, user_profile)
    except Exception as e:
        ctx.logger.exception("[resume-agent] unhandled_resume_generation_error")
        await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=[TextContent(type="text", text=f"❌ Error during resume generation: {e}")]))

@resume_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}")

agent.include(resume_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)
set_on_payment_verified(_on_payment_verified)

if __name__ == "__main__":
    agent.run()

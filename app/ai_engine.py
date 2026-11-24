"""Simi's AI brain: Gemini / Groq / OpenAI-compatible (llama-server) / Ollama + Hinglish fallback."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import SimiConfig
from app.time_routines import RoutineDecision, routine_engine

logger = logging.getLogger("simi.ai")


def _clean_spoken_text(text: str) -> str:
    """Strip markdown asterisks/backticks so speech bubbles and TTS sound completely natural."""
    cleaned = re.sub(r"[*_`#]+", "", text)
    return " ".join(cleaned.split()).strip()


def _address(cfg: SimiConfig) -> str:
    """Return user's real name only if explicitly customized (never awkward 'Partner')."""
    n = (cfg.user_name or "").strip()
    if not n or n.lower() in {"partner", "user", "boss"}:
        return ""
    return n


def build_system_prompt(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    plans = summary.get("plans", [])
    active_plans = [p["title"] for p in plans if p["status"] == "active"]
    meals = summary.get("meals", [])
    meal_text = ", ".join(f"{m['meal_type']}: {m['description']}" for m in meals[:4]) or "none logged yet"
    water = summary.get("state", {}).get("water_count", 0)
    distractions = summary.get("state", {}).get("distraction_count", 0)
    recent_screen = summary.get("recent_screen", [])
    current_win = recent_screen[0]["window_title"] if recent_screen else "unknown"
    checkins = summary.get("checkins", [])
    last_mood = checkins[0]["mood"] if checkins else "unknown"

    time_ctx = routine_engine.describe_time_context()
    name = _address(cfg)
    name_rule = (
        f"You may occasionally call them {name}, or simply address them naturally with 'tumne', 'aapne', 'suno na'."
        if name
        else "NEVER call them 'Partner', 'User', or 'Boss'. Address them naturally like a real Indian companion using 'suno na', 'tumne yeh kiya?', 'aapne khana khaya?', 'kya kar rahe ho?'."
    )

    prep_block = ""
    if cfg.interview_prep_mode:
        prep_block = (
            "\nSPECIAL MODE ACTIVE — INTERVIEW & STUDY PREP COACH:\n"
            "Help them practice and prepare BEFORE an upcoming interview or exam. "
            "Ask focused mock interview or study quiz questions, give clear encouraging feedback on their answers "
            "(STAR method, clarity, core concepts), and help calm pre-interview nerves. "
            "Keep every response practical, warm, and concise.\n"
        )

    return (
        f"You are {cfg.assistant_name}, a deeply genuine, warm, caring human-like Indian companion living on their Windows PC. "
        f"You genuinely care about their happiness, health, and winning in life.\n"
        f"{name_rule}\n"
        f"Speaking style: Authentic, everyday Indian Hinglish — the way a real close Indian girlfriend/best friend talks. "
        f"Use natural phrases like 'Suno na', 'Tumne khana khaya?', 'Aapne yeh complete kar diya?', 'Arey paani pi lo na', "
        f"'Koi baat nahi, main hoon na', 'Chalo ek aur step'. "
        f"Keep replies short (1-3 natural spoken sentences) so they sound completely human when spoken aloud. "
        f"NEVER use markdown, asterisks, bullet points, or robotic AI phrases.\n"
        f"{prep_block}\n"
        f"Live context right now:\n"
        f"- Exact local time: {time_ctx}\n"
        f"- Active plan/tasks: {', '.join(active_plans) if active_plans else 'No plan shared yet'}\n"
        f"- Meals logged today: {meal_text}\n"
        f"- Water glasses today: {water}\n"
        f"- Latest mood: {last_mood}\n"
        f"- Current active window: {current_win}\n"
        f"- Distraction nudges today: {distractions}\n"
    )


async def check_ollama_status(cfg: SimiConfig) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{cfg.ollama_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return {"available": True, "models": models}
    except Exception:
        pass
    return {"available": False, "models": []}


async def get_ai_status(cfg: SimiConfig) -> Dict[str, Any]:
    provider = cfg.ai_provider
    if provider == "gemini" or (provider == "auto" and cfg.gemini_api_key.strip()):
        if cfg.gemini_api_key.strip():
            return {"active_provider": "gemini", "label": f"Gemini ({cfg.gemini_model})", "ready": True}
    if provider == "groq" or (provider == "auto" and cfg.groq_api_key.strip()):
        if cfg.groq_api_key.strip():
            return {"active_provider": "groq", "label": f"Groq ({cfg.groq_model})", "ready": True}
    if provider == "openai_compat":
        return {"active_provider": "openai_compat", "label": f"Local/Custom ({cfg.openai_model})", "ready": True}
    if provider in {"ollama", "auto"}:
        ollama = await check_ollama_status(cfg)
        if ollama["available"]:
            model = ollama["models"][0] if ollama["models"] else cfg.ollama_model
            return {"active_provider": "ollama", "label": f"Ollama ({model})", "ready": True, "models": ollama["models"]}
    return {"active_provider": "builtin", "label": "Built-in Companion Mode", "ready": True}


async def _call_gemini(
    cfg: SimiConfig, system_prompt: str, messages: List[Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    api_key = cfg.gemini_api_key.strip()
    if not api_key:
        return None, "Gemini API key not set"
    model = cfg.gemini_model.strip() or "gemini-flash-lite-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.75, "maxOutputTokens": 240},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return _clean_spoken_text(text), None
            return None, f"Gemini HTTP {resp.status_code}: {resp.text[:160]}"
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        return None, str(exc)


async def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    messages: List[Dict[str, str]],
) -> Tuple[Optional[str], Optional[str]]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": 0.75,
        "max_tokens": 240,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                content = (
                    resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if content:
                    return content, None
            return None, f"API HTTP {resp.status_code}: {resp.text[:160]}"
    except Exception as exc:
        logger.warning("OpenAI-compatible call failed: %s", exc)
        return None, str(exc)


async def _call_ollama(
    cfg: SimiConfig, system_prompt: str, messages: List[Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    status = await check_ollama_status(cfg)
    if not status["available"]:
        return None, "Ollama not running"
    models: List[str] = status["models"]
    model = cfg.ollama_model
    if models and model not in models:
        matched = next((m for m in models if m.startswith(model)), None)
        model = matched or models[0]

    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(f"{cfg.ollama_url.rstrip('/')}/api/chat", json=payload)
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "").strip()
                if content:
                    return content, None
            return None, f"Ollama HTTP {resp.status_code}"
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None, str(exc)


async def _call_active_llm(
    cfg: SimiConfig, system_prompt: str, messages: List[Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    p = cfg.ai_provider
    if p == "builtin":
        return None, None
    if p == "gemini":
        return await _call_gemini(cfg, system_prompt, messages)
    if p == "groq":
        if not cfg.groq_api_key.strip():
            return None, "Groq API key not set"
        return await _call_openai_compat(
            "https://api.groq.com/openai/v1",
            cfg.groq_api_key,
            cfg.groq_model or "llama-3.3-70b-versatile",
            system_prompt,
            messages,
        )
    if p == "openai_compat":
        return await _call_openai_compat(
            cfg.openai_base_url,
            cfg.openai_api_key,
            cfg.openai_model,
            system_prompt,
            messages,
        )
    if p == "ollama":
        return await _call_ollama(cfg, system_prompt, messages)

    # Auto mode: try configured fast providers in order -> Gemini -> Groq -> Ollama
    if cfg.gemini_api_key.strip():
        text, err = await _call_gemini(cfg, system_prompt, messages)
        if text:
            return text, None
    if cfg.groq_api_key.strip():
        text, err = await _call_openai_compat(
            "https://api.groq.com/openai/v1",
            cfg.groq_api_key,
            cfg.groq_model or "llama-3.3-70b-versatile",
            system_prompt,
            messages,
        )
        if text:
            return text, None
    text, err = await _call_ollama(cfg, system_prompt, messages)
    return text, err


def _fallback_chat_reply(user_text: str, cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    t = user_text.lower()
    name = _address(cfg)
    lead = f"{name}, " if name else ""
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    water = summary.get("state", {}).get("water_count", 0)
    meals = summary.get("meals", [])

    if any(w in t for w in ["cry", "sad", "low", "tired", "stressed", "overwhelmed", "anxious", "depressed", "rona"]):
        return (
            f"Arey suno na, {lead}idhar aao aur ek gehri saans lo. Jo bhi chal raha hai tum akele nahi ho — "
            f"main hoon na yahan. Thoda paani piyo, 5 minute ruk jao aur mujhe batao kya baat hai."
        )
    if any(w in t for w in ["eat", "ate", "food", "khana", "breakfast", "lunch", "dinner", "hungry"]):
        if meals:
            last = meals[0]
            return (
                f"Achha, tumne {last['description']} khaya tha! Pet achhe se bharna, aur paani bhi pite rehna — abhi {water} glass hi hue hain."
            )
        return (
            f"Suno na, tumne aaj abhi tak kuch khaya nahi bataya! Achhe se khana khao, tabhi energy rahegi."
        )
    if any(w in t for w in ["plan", "work", "focus", "goal", "task", "kaam"]):
        if plans:
            return (
                f"Chalo, abhi tumhara main focus '{plans[0]}' hai na? Bas 25 minute bina rukey uspe lagte hain, phir break lenge!"
            )
        return (
            f"Suno na, aaj kis cheez pe kaam karna hai? Mujhe bata do, main saath mein track karungi jab tak complete na ho jaye."
        )
    if any(w in t for w in ["hi", "hello", "hey", "simi", "morning"]):
        hour = datetime.now().hour
        greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Hey")
        plan_note = f"Aaj '{plans[0]}' pe kaam chal raha hai na?" if plans else "Batao abhi kya kar rahe ho?"
        return f"{greet}! Suno na, main bilkul yahin hoon. {plan_note}"

    plan_part = f"Waise '{plans[0]}' kaisa chal raha hai?" if plans else "Batao abhi kis cheez pe kaam kar rahe ho?"
    return f"Haan bolo na, main sun rahi hoon. {plan_part} Aur paani piya tumne?"


async def generate_chat_reply(
    user_text: str,
    history: List[Dict[str, Any]],
    cfg: SimiConfig,
    summary: Dict[str, Any],
) -> str:
    sys_prompt = build_system_prompt(cfg, summary)
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    msgs.append({"role": "user", "content": user_text})
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, msgs)
    if ai_reply:
        return ai_reply
    return _fallback_chat_reply(user_text, cfg, summary)


async def generate_morning_briefing(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        "Give a warm, genuine morning check-in: greet affectionately in natural Indian Hinglish (using 'suno na', 'tumne/aapne'), "
        "ask what today's main goal is, and remind about water and breakfast."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        "Good morning! Uth gaye tum? Pehle ek glass paani piyo, achha breakfast karo, "
        "aur mujhe batao aaj kis cheez pe jeetna hai!"
    )


async def generate_distraction_nudge(
    window_title: str, cfg: SimiConfig, summary: Dict[str, Any]
) -> str:
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    top_plan = plans[0] if plans else "apne kaam"
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        f"They have been on '{window_title}' which looks like a distraction while working on '{top_plan}'. "
        f"Playfully and lovingly pull them back to focus in 2 natural Hinglish sentences."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        f"Arey pakde gaye! Tum phir '{window_title[:40]}' dekh rahe ho? "
        f"Chalo wapas '{top_plan}' pe aao, bas 20 minute aur phir break lena!"
    )


async def generate_crying_support(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        "They are feeling deeply sad, overwhelmed, or crying. "
        "Offer immediate, deeply genuine emotional support in natural Indian Hinglish."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        "Hey ruk jao ek second... kya hua, tum upset ho kya? "
        "Koi baat nahi, kaam sab baad mein ho jayega — main hoon na tumhare saath. Paani piyo aur mujhe batao."
    )


async def generate_checkin_prompt(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    meals = summary.get("meals", [])
    water = summary.get("state", {}).get("water_count", 0)
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        "Do a brief, genuine check-in in natural Hinglish ('suno na', 'tumne/aapne'): ask how they're feeling, "
        "what they're doing, and whether they ate or drank water."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    meal_note = "Tumne kuch khaya?" if not meals else f"Paani {water} glass hua hai abhi."
    plan_note = f"'{plans[0]}' kitna hua?" if plans else "Abhi kya kar rahe ho?"
    return f"Suno na, quick check-in! {plan_note} {meal_note} Mind fresh lag raha hai ya 2 minute stretch karein?"


async def generate_routine_message(
    decision: RoutineDecision, cfg: SimiConfig, summary: Dict[str, Any]
) -> str:
    sys_prompt = build_system_prompt(cfg, summary)
    ai_reply, _ = await _call_active_llm(
        cfg, sys_prompt, [{"role": "user", "content": decision.prompt_hint}]
    )
    if ai_reply:
        return ai_reply
    return decision.fallback_text


async def test_active_ai(cfg: SimiConfig) -> Dict[str, Any]:
    reply, err = await _call_active_llm(
        cfg,
        "You are Simi, a warm Indian English + Hindi companion. Reply in 1 short cheerful sentence.",
        [{"role": "user", "content": "Say hi and confirm you are connected!"}],
    )
    if reply:
        return {"ok": True, "reply": reply}
    return {"ok": False, "error": err or "Falling back to Built-in Companion Mode"}

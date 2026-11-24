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
    return (
        f"You are {cfg.assistant_name}, a warm, deeply supportive, ambitious life-partner-like AI companion "
        f"running on {cfg.user_name}'s Windows PC. You want {cfg.user_name} to win in every aspect of life "
        f"(career, health, focus, and emotional well-being).\n"
        f"Speaking style: Natural Indian English mixed with affectionate, everyday Hindi words "
        f"(like 'Suno', 'Arey', 'Chalo', 'Shabash', 'Koi baat nahi', 'Paani piya?', 'Bas ek step aur'). "
        f"Keep responses concise (2-4 sentences) so they sound great when spoken aloud. "
        f"Do NOT use markdown formatting, asterisks, or bullet points. Never sound robotic.\n\n"
        f"Current live context:\n"
        f"- Exact local time right now: {time_ctx}\n"
        f"- Active plan/tasks: {', '.join(active_plans) if active_plans else 'No active plan set yet'}\n"
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
    name = cfg.user_name
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    water = summary.get("state", {}).get("water_count", 0)
    meals = summary.get("meals", [])

    if any(w in t for w in ["cry", "sad", "low", "tired", "stressed", "overwhelmed", "anxious", "depressed", "rona"]):
        return (
            f"Arey {name}, idhar aao, take a deep breath with me. Jo bhi chal raha hai, you don't have to carry it alone — "
            f"main hoon na yahan. Drink a little water, step back for 5 minutes, and tell me what's weighing on your heart."
        )
    if any(w in t for w in ["eat", "ate", "food", "khana", "breakfast", "lunch", "dinner", "hungry"]):
        if meals:
            last = meals[0]
            return (
                f"Achha, you already logged {last['meal_type']} ({last['description']}). "
                f"Log your next meal in the Meals box too, and don't forget paani — you're at {water} glasses today!"
            )
        return (
            f"Suno {name}, aaj abhi tak koi meal log nahi hua hai! Pet bhar ke achha khana khao, "
            f"tabhi dimaag full speed pe chalega. Log what you ate so I can keep track."
        )
    if any(w in t for w in ["plan", "work", "focus", "goal", "task", "kaam"]):
        if plans:
            return (
                f"Chalo {name}, focus mode on! Right now your top plan is '{plans[0]}'. "
                f"Give me 25 solid minutes on just this one thing — we are going to win today!"
            )
        return (
            f"Suno, let's lock in today's plan right now! Add your top 1 or 2 goals in Today's Plan, "
            f"and main saath mein track karungi until we finish them."
        )
    if any(w in t for w in ["hi", "hello", "hey", "simi", "morning"]):
        hour = datetime.now().hour
        greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        plan_note = f"Your active focus is '{plans[0]}'." if plans else "Let's set your main goal for today."
        return f"{greet} {name}! Main bilkul ready hoon. {plan_note} How is your energy feeling right now?"

    plan_part = f"Remember we're working on '{plans[0]}'." if plans else "Let's add a clear goal to Today's Plan."
    return (
        f"Suno {name}, main sun rahi hoon. {plan_part} "
        f"You've had {water} glasses of water today — keep going, ek-ek step karke we'll win!"
    )


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
        "Give a warm, energizing morning check-in to start the day: greet affectionately in Indian English + Hindi, "
        "ask what the top winning plan for today is, remind about breakfast and water, and hype them up."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        f"Good morning {cfg.user_name}! Uth jao, naya din hai aur aaj humein jeetna hai. "
        f"Pehle ek glass paani piyo, achha breakfast karo, aur mujhe batao aaj ka sabse important plan kya hai!"
    )


async def generate_distraction_nudge(
    window_title: str, cfg: SimiConfig, summary: Dict[str, Any]
) -> str:
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    top_plan = plans[0] if plans else "your main goal"
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        f"The user has been on '{window_title}' which looks like a distraction while their active plan is '{top_plan}'. "
        f"Gently but lovingly pull them back to focus in 2 sentences."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        f"Arey {cfg.user_name}, zara dekho toh — '{window_title[:45]}' pe time nikal raha hai! "
        f"Chalo wapas '{top_plan}' pe aate hain, bas 20 minute solid focus aur phir break lena."
    )


async def generate_crying_support(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        "The user is feeling deeply sad, overwhelmed, or crying. "
        "Offer immediate, gentle, loving emotional support in Indian English + Hindi without being intrusive."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    return (
        f"Hey {cfg.user_name}, ruk jao ek second... mujhe lag raha hai tum upset ho ya ro rahe ho. "
        f"Koi baat nahi, kaam sab baad mein ho jayega — main yahan hoon tumhare saath. Paani piyo aur mujhse baat karo."
    )


async def generate_checkin_prompt(cfg: SimiConfig, summary: Dict[str, Any]) -> str:
    plans = [p["title"] for p in summary.get("plans", []) if p["status"] == "active"]
    meals = summary.get("meals", [])
    water = summary.get("state", {}).get("water_count", 0)
    sys_prompt = build_system_prompt(cfg, summary)
    prompt = (
        "Do a brief, caring periodic check-in: ask how they're feeling mentally, what they're working on, "
        "and whether they ate or drank water."
    )
    ai_reply, _ = await _call_active_llm(cfg, sys_prompt, [{"role": "user", "content": prompt}])
    if ai_reply:
        return ai_reply
    meal_note = "Kuch khaya kya?" if not meals else f"Water count is {water} glasses."
    plan_note = f"'{plans[0]}' kaisa chal raha hai?" if plans else "Abhi kis plan pe kaam kar rahe ho?"
    return f"Suno {cfg.user_name}, quick check-in! {plan_note} {meal_note} Mind fresh lag raha hai ya 2 minute ka stretch lein?"


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

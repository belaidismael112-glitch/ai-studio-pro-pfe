from __future__ import annotations

LAYOUTS = ['professional_headshot', 'founder_profile_card', 'speaker_event_visual', 'personal_brand_cover', 'editorial_portrait', 'corporate_id_board']
DEFAULT_DENOISE = 0.3
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
MODE_MARKER = 'AI_STUDIO_V11_IDENTITY_PERSON_LAYER'

def choose_layout(category: str, prompt: str, rng):
    text = (prompt or "").lower()
    category = (category or "generic_product").lower()
    weighted = []
    if any(w in text for w in ("headshot","cv","linkedin","professional")):
        weighted += ["professional_headshot", "corporate_id_board"] * 5
    if any(w in text for w in ("speaker","event","conference")):
        weighted += ["speaker_event_visual", "founder_profile_card"] * 4
    if any(w in text for w in ("brand","cover","profile")):
        weighted += ["personal_brand_cover", "editorial_portrait"] * 4

    weighted += list(LAYOUTS) * 2
    return rng.choice(weighted or list(LAYOUTS))

def brief(subject: str, category: str, mood: str, user_direction: str, title: str, subtitle: str, cta: str) -> str:
    subject = subject or "uploaded subject"
    category = category or "generic_product"
    mood = mood or "premium commercial"
    user_direction = (user_direction or "").strip()[:260]
    return (
        f"Identity-safe person image. Preserve facial identity, age, face geometry and recognizable features. Improve background, lighting, outfit/style only if requested. "
        f"Selected identity layout keeps text away from face. Mood: {mood}. User direction: {user_direction}."
    )


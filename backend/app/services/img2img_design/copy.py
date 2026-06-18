from __future__ import annotations

from dataclasses import dataclass

from .utils import clean_badge, clean_bullets, clean_cta, clean_subtitle, clean_title


@dataclass
class CopyPack:
    badge: str
    title: str
    subtitle: str
    cta: str
    bullets: list[str]


CATEGORY_COPY = {
    "handbag": dict(title="THE LEATHER CARRY EDIT", subtitle="Black leather, gold hardware, and a refined silhouette for day-to-night styling.", bullets=["Soft leather", "Gold chain detail", "Day-to-night shape"], cta="SHOP THE EDIT"),
    "watch": dict(title="TIMELESS WRIST EDIT", subtitle="Refined lines, warm textures, and a classic profile made for daily wear.", bullets=["Automatic detail", "Refined case", "Everyday elegance"], cta="SHOP THE WATCH"),
    "cosmetics": dict(title="BEAUTY ESSENTIAL EDIT", subtitle="Clean presentation, soft light, and a premium routine-ready finish.", bullets=["Glow finish", "Clean formula", "Daily ritual"], cta="DISCOVER MORE"),
    "bottle": dict(title="SIGNATURE BOTTLE DROP", subtitle="A premium product scene built around rich color and polished shelf appeal.", bullets=["Bold flavor", "Premium bottle", "Campaign ready"], cta="SHOP NOW"),
    "food": dict(title="FRESH TASTE STORY", subtitle="Warm detail, appetizing texture, and a social-ready campaign frame.", bullets=["Fresh detail", "Rich texture", "Made to crave"], cta="ORDER NOW"),
    "tech": dict(title="SMART PRODUCT DROP", subtitle="Clean geometry, crisp detail, and modern launch-ready presentation.", bullets=["Sharp detail", "Modern design", "Launch ready"], cta="EXPLORE NOW"),
    "general_product": dict(title="PREMIUM PRODUCT EDIT", subtitle="A polished campaign visual with refined details and clean commercial styling.", bullets=["Premium finish", "Authentic detail", "Campaign ready"], cta="SHOP NOW"),
}


def build_copy(plan, category: str) -> CopyPack:
    brief = getattr(plan, "brief", None)
    preset = CATEGORY_COPY.get(category, CATEGORY_COPY["general_product"])
    return CopyPack(
        badge=clean_badge(getattr(brief, "badge", None), "NEW ARRIVAL").upper(),
        title=clean_title(None if (getattr(brief, "title", None) or "").upper() in {"PREMIUM PRODUCT EDITORIAL", "DESIGNED TO STAND OUT", "CAMPAIGN READY VISUAL"} else getattr(brief, "title", None), preset["title"]).upper(),
        subtitle=clean_subtitle(None if "premium styling" in (getattr(brief, "subtitle", None) or "").lower() else getattr(brief, "subtitle", None), preset["subtitle"]),
        cta=clean_cta(None if (getattr(brief, "cta", None) or "").upper() in {"SHOP THE LOOK", "DISCOVER MORE"} else getattr(brief, "cta", None), preset["cta"]).upper(),
        bullets=[b.upper() for b in clean_bullets(getattr(brief, "bullets", None), preset["bullets"])],
    )

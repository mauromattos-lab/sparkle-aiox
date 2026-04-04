"""
Content Engine v2 — Templates by format and platform.

Each template defines the structure, prompt instructions, and constraints
for generating content in a specific format on a specific platform.

All templates are in Brazilian Portuguese.
"""
from __future__ import annotations

from runtime.content.models import ContentFormat, Platform


# ── Template data class ──────────────────────────────────────

class ContentTemplate:
    """Defines generation structure for a content format + platform combination."""

    def __init__(
        self,
        format: ContentFormat,
        platform: Platform,
        name: str,
        description: str,
        structure: list[dict],
        prompt_instructions: str,
        max_length: int | None = None,
        slide_count: tuple[int, int] | None = None,
    ):
        self.format = format
        self.platform = platform
        self.name = name
        self.description = description
        self.structure = structure
        self.prompt_instructions = prompt_instructions
        self.max_length = max_length
        self.slide_count = slide_count

    def to_dict(self) -> dict:
        return {
            "format": self.format.value,
            "platform": self.platform.value,
            "name": self.name,
            "description": self.description,
            "structure": self.structure,
            "max_length": self.max_length,
            "slide_count": self.slide_count,
        }


# ── Instagram Templates ──────────────────────────────────────

TEMPLATE_INSTAGRAM_POST = ContentTemplate(
    format=ContentFormat.POST,
    platform=Platform.INSTAGRAM,
    name="Post Instagram",
    description="Post de imagem unica com legenda otimizada para engajamento",
    structure=[
        {"section": "hook", "label": "Gancho (1a linha)", "max_chars": 150},
        {"section": "body", "label": "Corpo (3-5 paragrafos curtos)", "max_chars": 1800},
        {"section": "cta", "label": "Call-to-Action", "max_chars": 200},
    ],
    prompt_instructions=(
        "Escreva uma legenda para Post de Instagram com:\n"
        "- Abertura impactante (1a linha = gancho que para o scroll)\n"
        "- Corpo: 3-5 paragrafos curtos, um conceito por paragrafo\n"
        "- Use quebras de linha para respiro visual\n"
        "- CTA claro no final (salve, compartilhe, comente)\n"
        "- Maximo 2200 caracteres\n"
        "- Nao inclua hashtags no corpo — liste ao final separado por '---HASHTAGS---'"
    ),
    max_length=2200,
)

TEMPLATE_INSTAGRAM_CAROUSEL = ContentTemplate(
    format=ContentFormat.CAROUSEL,
    platform=Platform.INSTAGRAM,
    name="Carrossel Instagram",
    description="Carrossel educativo com capa + slides de conteudo + CTA final",
    structure=[
        {"section": "cover", "label": "Slide 1 — Capa/Gancho", "max_chars": 80},
        {"section": "content_slide", "label": "Slides 2-6 — Conteudo", "max_chars": 120, "repeat": "2-6"},
        {"section": "cta_slide", "label": "Slide Final — CTA", "max_chars": 100},
        {"section": "caption", "label": "Legenda do post", "max_chars": 800},
    ],
    prompt_instructions=(
        "Crie um carrossel de Instagram com 5-7 slides:\n"
        "- Slide 1 (CAPA): titulo/gancho impactante (max 10 palavras, fonte grande)\n"
        "- Slides 2-6 (CONTEUDO): um insight por slide (1-2 frases cada, texto legivel)\n"
        "- Slide Final (CTA): chamada para acao clara\n"
        "- LEGENDA: texto complementar para o corpo do post (max 800 chars)\n\n"
        "Formato de saida:\n"
        "SLIDE 1:\n[texto da capa]\n\n"
        "SLIDE 2:\n[conteudo]\n\n"
        "...\n\n"
        "LEGENDA:\n[texto da legenda]\n\n"
        "---HASHTAGS---\n[hashtags separadas por espaco]"
    ),
    max_length=None,
    slide_count=(5, 10),
)

TEMPLATE_INSTAGRAM_REELS = ContentTemplate(
    format=ContentFormat.REELS,
    platform=Platform.INSTAGRAM,
    name="Reels Instagram",
    description="Roteiro de video curto com hook + corpo + CTA (9:16, ate 90s)",
    structure=[
        {"section": "hook", "label": "Hook (0-3s)", "max_chars": 50, "duration": "0-3s"},
        {"section": "body", "label": "Corpo (3-60s)", "max_chars": 500, "duration": "3-60s"},
        {"section": "cta", "label": "CTA Final (ultimos 5s)", "max_chars": 80, "duration": "5s"},
        {"section": "caption", "label": "Legenda", "max_chars": 2200},
        {"section": "audio_suggestion", "label": "Sugestao de audio/musica", "max_chars": 100},
    ],
    prompt_instructions=(
        "Crie um roteiro de Reels para Instagram (video vertical 9:16, ate 90 segundos):\n\n"
        "HOOK (0-3 segundos):\n"
        "- Frase que prende atencao IMEDIATAMENTE\n"
        "- Pode ser pergunta, afirmacao chocante ou promessa\n\n"
        "CORPO (3-60 segundos):\n"
        "- Desenvolvimento do tema em bullets curtos\n"
        "- Cada bullet = 1 corte/cena\n"
        "- Linguagem falada, nao escrita\n\n"
        "CTA (ultimos 5 segundos):\n"
        "- Acao clara: seguir, salvar, comentar\n\n"
        "LEGENDA:\n"
        "- Texto complementar para quem le sem audio\n\n"
        "AUDIO:\n"
        "- Sugestao de musica/audio trending\n\n"
        "---HASHTAGS---\n[hashtags]"
    ),
    max_length=None,
)

TEMPLATE_INSTAGRAM_STORY = ContentTemplate(
    format=ContentFormat.STORY,
    platform=Platform.INSTAGRAM,
    name="Story Instagram",
    description="Conteudo efemero (24h) — texto curto + sticker/enquete",
    structure=[
        {"section": "text", "label": "Texto principal", "max_chars": 200},
        {"section": "sticker", "label": "Sugestao de sticker/enquete", "max_chars": 100},
        {"section": "background", "label": "Sugestao de fundo", "max_chars": 50},
    ],
    prompt_instructions=(
        "Escreva conteudo para Story de Instagram (24h, vertical 9:16):\n\n"
        "TEXTO:\n"
        "- Maximo 200 caracteres\n"
        "- Impactante, acao imediata ou pergunta provocativa\n"
        "- Fonte grande, legivel em mobile\n\n"
        "STICKER:\n"
        "- Sugestao de interacao: enquete, pergunta, quiz, emoji slider\n"
        "- Texto do sticker\n\n"
        "FUNDO:\n"
        "- Sugestao de cor ou tipo de fundo\n\n"
        "Sem hashtags em stories."
    ),
    max_length=200,
)

# ── YouTube Templates ─────────────────────────────────────────

TEMPLATE_YOUTUBE_SHORTS = ContentTemplate(
    format=ContentFormat.SHORTS,
    platform=Platform.YOUTUBE,
    name="YouTube Shorts",
    description="Video vertical curto para YouTube (ate 60s, 9:16)",
    structure=[
        {"section": "hook", "label": "Hook (0-3s)", "max_chars": 50, "duration": "0-3s"},
        {"section": "body", "label": "Corpo (3-50s)", "max_chars": 400, "duration": "3-50s"},
        {"section": "cta", "label": "CTA + Subscribe (ultimos 5s)", "max_chars": 80, "duration": "5s"},
        {"section": "title", "label": "Titulo do Short", "max_chars": 100},
        {"section": "description", "label": "Descricao", "max_chars": 500},
    ],
    prompt_instructions=(
        "Crie um roteiro de YouTube Shorts (video vertical 9:16, ate 60 segundos):\n\n"
        "TITULO:\n"
        "- Titulo curto e clickbait-positivo (max 100 chars)\n\n"
        "HOOK (0-3 segundos):\n"
        "- Frase que prende atencao — YouTube corta rapido se nao engajar\n\n"
        "CORPO (3-50 segundos):\n"
        "- Desenvolvimento em bullets (cada bullet = 1 corte)\n"
        "- Ritmo rapido, sem enrolacao\n"
        "- Linguagem falada, energetica\n\n"
        "CTA (ultimos 5 segundos):\n"
        "- Inscreva-se + acao especifica\n\n"
        "DESCRICAO:\n"
        "- Texto complementar com contexto\n\n"
        "---HASHTAGS---\n[max 5 hashtags relevantes]"
    ),
    max_length=None,
)

# ── TikTok Templates ─────────────────────────────────────────

TEMPLATE_TIKTOK_REELS = ContentTemplate(
    format=ContentFormat.REELS,
    platform=Platform.TIKTOK,
    name="TikTok Video",
    description="Video vertical para TikTok (ate 3min, 9:16)",
    structure=[
        {"section": "hook", "label": "Hook (0-2s)", "max_chars": 40, "duration": "0-2s"},
        {"section": "body", "label": "Corpo (2-60s)", "max_chars": 500, "duration": "2-60s"},
        {"section": "cta", "label": "CTA (ultimos 3s)", "max_chars": 60, "duration": "3s"},
        {"section": "caption", "label": "Legenda", "max_chars": 2200},
        {"section": "sound_suggestion", "label": "Sugestao de som trending", "max_chars": 100},
    ],
    prompt_instructions=(
        "Crie um roteiro de video para TikTok (vertical 9:16, idealmente 30-60 segundos):\n\n"
        "HOOK (0-2 segundos):\n"
        "- TikTok e IMPIEDOSO — prenda em 2 segundos ou perde\n"
        "- Pergunta direta, revelacao, ou 'voce sabia que...'\n\n"
        "CORPO (2-60 segundos):\n"
        "- Bullets rapidos, cada um = 1 corte\n"
        "- Tom conversacional, como se falasse com amigo\n"
        "- Ritmo TikTok: rapido, sem pause longas\n\n"
        "CTA (ultimos 3 segundos):\n"
        "- Seguir, curtir, ou comentar algo especifico\n\n"
        "LEGENDA:\n"
        "- Curta, com gancho que complementa o video\n\n"
        "SOM:\n"
        "- Sugestao de som/musica trending no TikTok\n\n"
        "---HASHTAGS---\n[max 5 hashtags — TikTok favorece poucas e relevantes]"
    ),
    max_length=None,
)


# ── Template registry ────────────────────────────────────────

_TEMPLATES: dict[tuple[ContentFormat, Platform], ContentTemplate] = {
    (ContentFormat.POST, Platform.INSTAGRAM): TEMPLATE_INSTAGRAM_POST,
    (ContentFormat.CAROUSEL, Platform.INSTAGRAM): TEMPLATE_INSTAGRAM_CAROUSEL,
    (ContentFormat.REELS, Platform.INSTAGRAM): TEMPLATE_INSTAGRAM_REELS,
    (ContentFormat.STORY, Platform.INSTAGRAM): TEMPLATE_INSTAGRAM_STORY,
    (ContentFormat.SHORTS, Platform.YOUTUBE): TEMPLATE_YOUTUBE_SHORTS,
    (ContentFormat.REELS, Platform.TIKTOK): TEMPLATE_TIKTOK_REELS,
}

# Backward compat: map old v1 format strings to (format, platform) tuples
_V1_FORMAT_MAP: dict[str, tuple[ContentFormat, Platform]] = {
    "instagram_post": (ContentFormat.POST, Platform.INSTAGRAM),
    "carousel": (ContentFormat.CAROUSEL, Platform.INSTAGRAM),
    "story": (ContentFormat.STORY, Platform.INSTAGRAM),
    "thread": (ContentFormat.THREAD, Platform.INSTAGRAM),
}


def get_template(
    fmt: ContentFormat | str,
    platform: Platform | str = Platform.INSTAGRAM,
) -> ContentTemplate | None:
    """Look up a content template by format + platform.

    Accepts both enum values and plain strings for backward compat.
    Falls back to v1 format strings (e.g. 'instagram_post').
    """
    # Handle string inputs
    if isinstance(fmt, str):
        # Try v1 map first
        if fmt in _V1_FORMAT_MAP:
            v1_fmt, v1_platform = _V1_FORMAT_MAP[fmt]
            return _TEMPLATES.get((v1_fmt, v1_platform))
        try:
            fmt = ContentFormat(fmt)
        except ValueError:
            return None

    if isinstance(platform, str):
        try:
            platform = Platform(platform)
        except ValueError:
            return None

    return _TEMPLATES.get((fmt, platform))


def list_templates() -> list[dict]:
    """Return all available templates as dicts."""
    return [t.to_dict() for t in _TEMPLATES.values()]


def get_prompt_instructions(
    fmt: ContentFormat | str,
    platform: Platform | str = Platform.INSTAGRAM,
) -> str:
    """Return the prompt instructions for a given format+platform.

    Falls back to v1 _FORMAT_INSTRUCTIONS in generate_content.py if no v2 template.
    """
    template = get_template(fmt, platform)
    if template:
        return template.prompt_instructions
    # Fallback: return generic
    return (
        "Crie conteudo de alta qualidade para redes sociais.\n"
        "- Abertura impactante\n"
        "- Corpo com valor real\n"
        "- CTA claro\n"
        "- Hashtags ao final separadas por '---HASHTAGS---'"
    )

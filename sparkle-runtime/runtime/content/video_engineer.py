"""
Video Prompt Engineer — gera prompts de movimento para animação da Zenya via Veo.

Recebe imagem gerada + estilo e retorna prompt descrevendo:
  - Movimento da personagem (expressão, gesto)
  - Câmera (movimento, enquadramento)
  - Física do ambiente (luz, fundo)

Estilos suportados:
  - cinematic: push-in lento, movimento sutil, grão de filme
  - influencer_natural: head turn natural, sorriso, gesto casual
"""
from __future__ import annotations

CINEMATIC_PROMPT = (
    "Slow cinematic push-in on face, subtle hair movement in breeze, "
    "blink once naturally, bokeh background softly shifting, "
    "warm golden light, 24fps film grain. "
    "Character remains recognizable throughout."
)

INFLUENCER_NATURAL_PROMPT = (
    "Slight head turn towards camera, natural smile emerging, "
    "casual hand gesture, background slightly out of focus, "
    "bright natural light, smooth organic movement. "
    "Authentic and approachable expression."
)


def build_video_prompt(style: str, theme: str | None = None) -> str:
    """
    Constrói prompt de vídeo para animação da Zenya.

    Args:
        style: 'cinematic' | 'influencer_natural'
        theme: Tema opcional para contextualizar o movimento

    Returns:
        Prompt de movimento para o Veo
    """
    base = CINEMATIC_PROMPT if style == "cinematic" else INFLUENCER_NATURAL_PROMPT

    if theme:
        base = f"{base} Context: {theme}."

    return base


def get_video_duration(style: str) -> int:
    """Retorna duração em segundos conforme o estilo."""
    return 10 if style == "cinematic" else 5

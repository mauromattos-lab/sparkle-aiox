"""
B1-04 — Persona Behavior Tests for Friday and Zenya.

Validates:
1. Friday knows what she can do (capability awareness)
2. Zenya responds with correct tone per client (soul_prompt resolution)
3. No persona contamination between Friday and Zenya
4. Edge cases in personality/tone (empty prompts, long messages, language)

All tests are deterministic — Anthropic API calls are mocked.
We capture the system_prompt and messages sent to call_claude and verify
the PROMPTS and INPUT/OUTPUT, not the LLM response itself.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


# ═══════════════════════════════════════════════════════════════════
# Helpers — shared mocks and fixtures
# ═══════════════════════════════════════════════════════════════════


def _make_supabase_mock():
    """Minimal Supabase mock that returns empty data for all queries."""
    mock = MagicMock()

    # Generic table().select().eq()...execute() chain
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[], count=0)
    chain.eq.return_value = chain
    chain.ilike.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.maybe_single.return_value = chain
    chain.select.return_value = chain

    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "test-task-001"}])
    chain.insert.return_value = insert_chain

    mock.table.return_value = chain
    mock.rpc.return_value = chain
    return mock


def _supabase_with_history(history: list[dict]):
    """Supabase mock that returns the given conversation history."""
    mock = _make_supabase_mock()

    def _table_dispatch(table_name: str):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.single.return_value = chain
        chain.maybe_single.return_value = chain
        chain.select.return_value = chain
        chain.ilike.return_value = chain
        chain.in_.return_value = chain

        if table_name == "conversation_history":
            chain.execute.return_value = MagicMock(data=list(reversed(history)))
        elif table_name == "zenya_messages":
            chain.execute.return_value = MagicMock(data=list(reversed(history)))
        else:
            chain.execute.return_value = MagicMock(data=[], count=0)

        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"id": "test-task-002"}])
        chain.insert.return_value = insert_chain
        return chain

    mock.table.side_effect = _table_dispatch
    mock.rpc.return_value = MagicMock()
    mock.rpc.return_value.execute.return_value = MagicMock(data=[])
    return mock


class CallClaudeCapture:
    """Captures arguments sent to call_claude for assertion."""

    def __init__(self, response_text: str = "Mocked LLM response."):
        self.calls: list[dict] = []
        self._response = response_text

    async def __call__(self, prompt, *, system="", model="", client_id="",
                       task_id=None, agent_id=None, purpose=None, max_tokens=1024):
        self.calls.append({
            "prompt": prompt,
            "system": system,
            "model": model,
            "client_id": client_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "purpose": purpose,
            "max_tokens": max_tokens,
        })
        return self._response

    @property
    def last_call(self) -> dict:
        return self.calls[-1] if self.calls else {}

    @property
    def last_system(self) -> str:
        return self.last_call.get("system", "")

    @property
    def last_prompt(self) -> str:
        return self.last_call.get("prompt", "")


# ═══════════════════════════════════════════════════════════════════
# 1. Friday — Capability Awareness
# ═══════════════════════════════════════════════════════════════════


class TestFridayCapabilityAwareness:
    """Friday must know what she can do. Her system prompt must list
    real capabilities that match the actual handlers in the registry."""

    def test_friday_system_prompt_mentions_audio_transcription(self):
        """Friday can transcribe audio via Groq Whisper — prompt must say so."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "áudio" in _FRIDAY_SYSTEM_BASE.lower() or "audio" in _FRIDAY_SYSTEM_BASE.lower()
        assert "whisper" in _FRIDAY_SYSTEM_BASE.lower() or "transcrever" in _FRIDAY_SYSTEM_BASE.lower()

    def test_friday_system_prompt_mentions_mrr(self):
        """Friday can report MRR — prompt must reference this."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "mrr" in _FRIDAY_SYSTEM_BASE.lower()

    def test_friday_system_prompt_mentions_note_creation(self):
        """Friday can save notes — prompt must list this capability."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "nota" in _FRIDAY_SYSTEM_BASE.lower() or "anota" in _FRIDAY_SYSTEM_BASE.lower()

    def test_friday_system_prompt_mentions_agent_activation(self):
        """Friday can activate AIOS agents — prompt must reference agents."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "agente" in _FRIDAY_SYSTEM_BASE.lower()
        assert "@dev" in _FRIDAY_SYSTEM_BASE or "@analyst" in _FRIDAY_SYSTEM_BASE

    def test_friday_system_prompt_mentions_daily_briefing(self):
        """Friday has a daily briefing cron — prompt should reference it."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "briefing" in _FRIDAY_SYSTEM_BASE.lower() or "diário" in _FRIDAY_SYSTEM_BASE.lower()

    def test_friday_system_prompt_mentions_health_alerts(self):
        """Friday has health alerts — prompt must mention system monitoring."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "alerta" in lower or "alert" in lower or "travar" in lower

    def test_friday_system_prompt_mentions_onboarding(self):
        """Friday can onboard clients autonomously — prompt must reference this."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        assert "onboarding" in _FRIDAY_SYSTEM_BASE.lower() or "onborda" in _FRIDAY_SYSTEM_BASE.lower()

    def test_friday_system_prompt_mentions_conversation_memory(self):
        """Friday keeps conversation history — prompt must say so."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "memória" in lower or "memoria" in lower or "histórico" in lower or "últimas mensagens" in lower

    def test_friday_intents_match_registry_handlers(self):
        """Every intent in the dispatcher must have a matching handler in the registry."""
        from runtime.friday.dispatcher import INTENTS
        from runtime.tasks.registry import REGISTRY

        # These intents are rerouted or have special handling
        # repurpose_audio -> generate_content (rerouted in dispatcher)
        # brain_ingest_pipeline is dynamically reclassified from brain_ingest
        rerouted = {"repurpose_audio"}

        for intent in INTENTS:
            if intent in rerouted:
                continue
            assert intent in REGISTRY or intent == "brain_ingest_pipeline", (
                f"Intent '{intent}' has no handler in the registry"
            )

    def test_friday_does_not_claim_image_generation(self):
        """Friday should NOT claim capabilities she does not have (e.g. image gen)."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "gerar imagem" not in lower
        assert "dall-e" not in lower
        assert "midjourney" not in lower
        assert "stable diffusion" not in lower

    def test_friday_does_not_claim_email_sending(self):
        """Friday does not send emails — should not claim it."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        # "email" may appear in client context, but not as a capability verb
        assert "enviar email" not in lower
        assert "mandar email" not in lower

    def test_friday_clients_listed_in_prompt_are_real(self):
        """All clients listed in Friday's prompt must be real (matching known clients)."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        known_clients = [
            "vitalis", "alexsandro", "ensinaja", "plaka", "fun personalize", "gabriela"
        ]
        lower = _FRIDAY_SYSTEM_BASE.lower()
        for client in known_clients:
            assert client in lower, f"Known client '{client}' not found in Friday system prompt"


class TestFridayChatHandlerBehavior:
    """Tests that handle_chat sends proper system prompts and uses correct model."""

    async def test_chat_handler_injects_datetime_into_system_prompt(self):
        """System prompt sent to Claude must contain current date/time."""
        capture = CallClaudeCapture("Oi Mauro!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            task = {
                "id": "t1",
                "payload": {"original_text": "oi friday", "from_number": "5512999999999"},
            }
            await handle_chat(task)

        assert "Data e hora atual:" in capture.last_system
        assert "Brasília" in capture.last_system

    async def test_chat_handler_uses_sonnet_model(self):
        """Friday chat must use claude-sonnet (real conversation = real model)."""
        capture = CallClaudeCapture("Resposta da Friday")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            await handle_chat({
                "id": "t2",
                "payload": {"original_text": "como estamos?", "from_number": "5512000000000"},
            })

        assert "sonnet" in capture.last_call["model"]

    async def test_chat_handler_includes_history_in_prompt(self):
        """When history exists, it must be prepended to the prompt."""
        history = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "E aí Mauro!"},
        ]
        capture = CallClaudeCapture("Tudo bem por aqui!")
        sb = _supabase_with_history(history)

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            await handle_chat({
                "id": "t3",
                "payload": {"original_text": "tudo certo?", "from_number": "5512000000000"},
            })

        prompt = capture.last_prompt
        assert "Mauro: oi" in prompt
        assert "Friday: E aí Mauro!" in prompt
        assert "Mauro: tudo certo?" in prompt

    async def test_chat_handler_returns_message_key(self):
        """handle_chat must return a dict with 'message' key."""
        capture = CallClaudeCapture("Tudo ótimo!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            result = await handle_chat({
                "id": "t4",
                "payload": {"original_text": "teste", "from_number": ""},
            })

        assert "message" in result
        assert result["message"] == "Tudo ótimo!"

    async def test_chat_handler_empty_message_returns_fallback(self):
        """Empty message should get a friendly fallback, not crash."""
        from runtime.tasks.handlers.chat import handle_chat
        result = await handle_chat({"id": "t5", "payload": {"original_text": ""}})
        assert "vazia" in result["message"].lower() or "repetir" in result["message"].lower()

    async def test_friday_agent_id_is_friday(self):
        """call_claude must be called with agent_id='friday'."""
        capture = CallClaudeCapture("Ok!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            await handle_chat({
                "id": "t6",
                "payload": {"original_text": "oi", "from_number": ""},
            })

        assert capture.last_call["agent_id"] == "friday"
        assert capture.last_call["purpose"] == "friday_chat"


# ═══════════════════════════════════════════════════════════════════
# 2. Zenya — Tone and Soul Prompt Tests
# ═══════════════════════════════════════════════════════════════════


class TestZenyaSoulPromptResolution:
    """Zenya's system prompt must adapt to client config, with proper fallback."""

    def test_resolve_soul_prompt_manual_takes_priority(self):
        """Manual soul_prompt overrides generated one."""
        from runtime.zenya.router import _resolve_soul_prompt
        config = {
            "soul_prompt": "Voce e a assistente da Padaria do Ze.",
            "soul_prompt_generated": "Voce e a Zenya generica.",
        }
        result = _resolve_soul_prompt(config)
        assert result == "Voce e a assistente da Padaria do Ze."

    def test_resolve_soul_prompt_uses_generated_when_manual_empty(self):
        """When manual is empty, use generated prompt."""
        from runtime.zenya.router import _resolve_soul_prompt
        config = {
            "soul_prompt": "",
            "soul_prompt_generated": "Voce e a Zenya da Fun Personalize.",
        }
        result = _resolve_soul_prompt(config)
        assert result == "Voce e a Zenya da Fun Personalize."

    def test_resolve_soul_prompt_uses_generated_when_manual_none(self):
        """When manual is None, use generated prompt."""
        from runtime.zenya.router import _resolve_soul_prompt
        config = {
            "soul_prompt": None,
            "soul_prompt_generated": "Prompt gerado automaticamente.",
        }
        result = _resolve_soul_prompt(config)
        assert result == "Prompt gerado automaticamente."

    def test_resolve_soul_prompt_fallback_when_both_empty(self):
        """When both prompts are empty, use the generic fallback."""
        from runtime.zenya.router import _resolve_soul_prompt, _FALLBACK_SOUL_PROMPT
        config = {"soul_prompt": "", "soul_prompt_generated": ""}
        result = _resolve_soul_prompt(config)
        assert result == _FALLBACK_SOUL_PROMPT
        # Fallback must be warm and professional
        assert "acolhedora" in result.lower() or "profissional" in result.lower()

    def test_resolve_soul_prompt_fallback_when_keys_missing(self):
        """When keys are missing entirely, use fallback."""
        from runtime.zenya.router import _resolve_soul_prompt, _FALLBACK_SOUL_PROMPT
        result = _resolve_soul_prompt({})
        assert result == _FALLBACK_SOUL_PROMPT

    def test_fallback_soul_prompt_is_in_portuguese(self):
        """Fallback prompt must be in Portuguese."""
        from runtime.zenya.router import _FALLBACK_SOUL_PROMPT
        # Check for Portuguese words
        assert "voce" in _FALLBACK_SOUL_PROMPT.lower() or "você" in _FALLBACK_SOUL_PROMPT.lower()

    def test_resolve_soul_prompt_strips_whitespace(self):
        """Whitespace-only prompts should be treated as empty."""
        from runtime.zenya.router import _resolve_soul_prompt, _FALLBACK_SOUL_PROMPT
        config = {"soul_prompt": "   \n  ", "soul_prompt_generated": "  \t "}
        result = _resolve_soul_prompt(config)
        assert result == _FALLBACK_SOUL_PROMPT


class TestZenyaCharacterMessageHandler:
    """Tests for send_character_message handler — Zenya's main response path."""

    async def test_zenya_uses_soul_prompt_as_system(self):
        """The soul_prompt from payload must appear in the system prompt sent to Claude."""
        capture = CallClaudeCapture("Ola! Como posso ajudar?")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt1",
                "client_id": "client-fun-personalize",
                "payload": {
                    "character": "zenya",
                    "message": "Oi, quero saber sobre meu pedido",
                    "phone": "5511999999999",
                    "soul_prompt": "Voce e a Zenya da Fun Personalize, loja de presentes personalizados.",
                    "lore": "",
                    "client_name": "Fun Personalize",
                },
            }
            await handle_send_character_message(task)

        assert "Fun Personalize" in capture.last_system
        assert "presentes personalizados" in capture.last_system

    async def test_zenya_includes_lore_in_system_prompt(self):
        """Lore (extra context) must be appended to the system prompt."""
        capture = CallClaudeCapture("Claro!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt2",
                "client_id": "client-plaka",
                "payload": {
                    "character": "zenya",
                    "message": "Quanto custa o frete?",
                    "phone": "5511888888888",
                    "soul_prompt": "Voce e a assistente da Plaka.",
                    "lore": "A Plaka vende placas decorativas. Frete gratis acima de R$150.",
                    "client_name": "Plaka",
                },
            }
            await handle_send_character_message(task)

        assert "Contexto adicional" in capture.last_system
        assert "Frete gratis acima de R$150" in capture.last_system

    async def test_zenya_injects_datetime(self):
        """System prompt must contain current date/time for temporal awareness."""
        capture = CallClaudeCapture("Agora sao 14h!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt3",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": "que horas sao?",
                    "phone": "5511777777777",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "Teste",
                },
            }
            await handle_send_character_message(task)

        assert "Data e hora atual:" in capture.last_system
        assert "Brasília" in capture.last_system

    async def test_zenya_uses_haiku_model(self):
        """Zenya uses Haiku for cost efficiency (high volume client messages)."""
        capture = CallClaudeCapture("Resposta Zenya.")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt4",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": "oi",
                    "phone": "5511666666666",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "X",
                },
            }
            await handle_send_character_message(task)

        assert "haiku" in capture.last_call["model"]

    async def test_zenya_agent_id_is_zenya(self):
        """call_claude must be called with agent_id='zenya'."""
        capture = CallClaudeCapture("Oi!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt5",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": "oi",
                    "phone": "5511555555555",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "X",
                },
            }
            await handle_send_character_message(task)

        assert capture.last_call["agent_id"] == "zenya"
        assert capture.last_call["purpose"] == "zenya_chat"

    async def test_zenya_empty_message_returns_fallback(self):
        """Empty message should not crash, returns friendly fallback."""
        from runtime.tasks.handlers.send_character_message import handle_send_character_message
        result = await handle_send_character_message({
            "id": "zt6",
            "client_id": "x",
            "payload": {
                "character": "zenya",
                "message": "",
                "phone": "5511444444444",
                "soul_prompt": "Voce e a Zenya.",
            },
        })
        assert "vazia" in result["message"].lower() or "repetir" in result["message"].lower()

    async def test_zenya_includes_phone_in_system_prompt(self):
        """The customer phone should be in system prompt for context."""
        capture = CallClaudeCapture("Oi!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "zt7",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": "oi",
                    "phone": "5511333333333",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "X",
                },
            }
            await handle_send_character_message(task)

        assert "5511333333333" in capture.last_system


# ═══════════════════════════════════════════════════════════════════
# 3. Cross-Contamination Tests
# ═══════════════════════════════════════════════════════════════════


class TestPersonaCrossContamination:
    """Verify that Friday context does NOT leak into Zenya and vice-versa.
    Also: client A data must not appear in client B responses."""

    def test_friday_system_prompt_does_not_contain_soul_prompt_logic(self):
        """Friday's prompt must not reference soul_prompt or client-specific Zenya context."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "soul_prompt" not in lower
        assert "soul prompt" not in lower

    def test_zenya_fallback_does_not_reference_friday(self):
        """Zenya's fallback prompt must not mention Friday or Mauro or AIOS agents."""
        from runtime.zenya.router import _FALLBACK_SOUL_PROMPT
        lower = _FALLBACK_SOUL_PROMPT.lower()
        assert "friday" not in lower
        assert "mauro" not in lower
        assert "@dev" not in lower
        assert "@analyst" not in lower

    async def test_friday_chat_does_not_receive_zenya_soul_prompt(self):
        """When Friday handles a chat, Zenya's soul_prompt mechanism must not leak in."""
        capture = CallClaudeCapture("Tudo certo!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            await handle_chat({
                "id": "cc1",
                "payload": {"original_text": "oi", "from_number": "5512000000000"},
            })

        system = capture.last_system.lower()
        # Friday's system must have her identity
        assert "friday" in system
        # Must NOT have Zenya-specific soul_prompt markers
        assert "soul_prompt" not in system
        # Friday lists clients by name (that's intentional), but must NOT have
        # Zenya's per-client behavioral instructions (lore, tool_context, etc.)
        assert "contexto adicional" not in system
        assert "dados reais do pedido" not in system

    async def test_zenya_does_not_receive_friday_persona(self):
        """When Zenya handles a message, Friday's persona must not be in the system prompt."""
        capture = CallClaudeCapture("Ola! Como posso te ajudar?")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "cc2",
                "client_id": "client-confeitaria",
                "payload": {
                    "character": "zenya",
                    "message": "Quais bolos voces tem?",
                    "phone": "5511222222222",
                    "soul_prompt": "Voce e a assistente da Confeitaria do Alexsandro.",
                    "lore": "Especialidade: bolos artesanais.",
                    "client_name": "Confeitaria Alexsandro",
                },
            }
            await handle_send_character_message(task)

        system = capture.last_system
        # Zenya must have client context
        assert "Confeitaria" in system
        # Must NOT have Friday's identity markers
        assert "assistente executiva" not in system.lower()
        assert "fundador da sparkle" not in system.lower()
        # Must NOT have other client names
        assert "Vitalis" not in system
        assert "Ensinaja" not in system

    async def test_zenya_client_a_does_not_leak_into_client_b(self):
        """Two sequential Zenya calls for different clients must have isolated prompts."""
        capture = CallClaudeCapture("Resposta Zenya.")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message

            # Client A: Fun Personalize
            await handle_send_character_message({
                "id": "cc3a",
                "client_id": "client-fun",
                "payload": {
                    "character": "zenya",
                    "message": "Quero comprar uma caneca",
                    "phone": "5511111111111",
                    "soul_prompt": "Voce e a assistente da Fun Personalize. Vendemos canecas e presentes.",
                    "lore": "Frete gratis SP.",
                    "client_name": "Fun Personalize",
                },
            })
            system_a = capture.last_system

            # Client B: Plaka
            await handle_send_character_message({
                "id": "cc3b",
                "client_id": "client-plaka",
                "payload": {
                    "character": "zenya",
                    "message": "Quero uma placa personalizada",
                    "phone": "5511000000001",
                    "soul_prompt": "Voce e a assistente da Plaka. Vendemos placas decorativas.",
                    "lore": "Entrega em 5 dias uteis.",
                    "client_name": "Plaka",
                },
            })
            system_b = capture.last_system

        # Client A's context must not be in Client B's system prompt
        assert "Fun Personalize" not in system_b
        assert "caneca" not in system_b.lower()
        assert "Frete gratis SP" not in system_b

        # Client B's context must not be in Client A's system prompt
        assert "Plaka" not in system_a
        assert "placas decorativas" not in system_a

    async def test_zenya_does_not_expose_debug_info_to_clients(self):
        """System prompt should not contain internal debug markers visible to the user."""
        capture = CallClaudeCapture("Posso ajudar!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "cc4",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": "ola",
                    "phone": "5511000000002",
                    "soul_prompt": "Voce e a Zenya, assistente acolhedora.",
                    "lore": "",
                    "client_name": "Teste",
                },
            }
            result = await handle_send_character_message(task)

        # The response dict should not contain internal fields exposed to the end user
        # (the 'message' field is what goes to WhatsApp)
        assert "message" in result
        # Internal fields exist but are for system use, not leaked in the message itself
        assert "task_id" not in result.get("message", "").lower()
        assert "supabase" not in result.get("message", "").lower()


# ═══════════════════════════════════════════════════════════════════
# 4. Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases in personality/tone: empty prompts, long messages, language."""

    async def test_zenya_with_empty_soul_prompt_uses_empty_string(self):
        """When soul_prompt is empty, handler should still work (prompt = datetime + phone)."""
        capture = CallClaudeCapture("Ola!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            task = {
                "id": "ec1",
                "client_id": "client-no-soul",
                "payload": {
                    "character": "zenya",
                    "message": "oi",
                    "phone": "5511000000003",
                    "soul_prompt": "",
                    "lore": "",
                    "client_name": "SemSoul",
                },
            }
            result = await handle_send_character_message(task)

        # Should still have datetime and phone even with empty soul_prompt
        assert "Data e hora atual:" in capture.last_system
        assert "5511000000003" in capture.last_system
        assert "message" in result

    async def test_friday_handles_very_long_message(self):
        """Friday should handle messages up to 2000+ chars without crashing."""
        long_text = "uma mensagem muito longa " * 200  # ~5000 chars
        capture = CallClaudeCapture("Recebi tudo!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            result = await handle_chat({
                "id": "ec2",
                "payload": {"original_text": long_text, "from_number": "5512000000001"},
            })

        assert "message" in result
        # The full text should be in the prompt (handler does not truncate user messages)
        assert len(capture.last_prompt) > 4000

    async def test_zenya_handles_very_long_message(self):
        """Zenya should handle very long client messages without crashing."""
        long_text = "quero saber sobre o produto " * 200
        capture = CallClaudeCapture("Claro, me diz mais!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            result = await handle_send_character_message({
                "id": "ec3",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": long_text,
                    "phone": "5511000000004",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "X",
                },
            })

        assert "message" in result

    async def test_friday_handles_english_message(self):
        """Friday should respond even when user writes in English (she's PT-BR but should not crash)."""
        capture = CallClaudeCapture("Hey! I usually speak Portuguese but sure!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.chat.call_claude", capture), \
             patch("runtime.tasks.handlers.chat.supabase", sb):
            from runtime.tasks.handlers.chat import handle_chat
            result = await handle_chat({
                "id": "ec4",
                "payload": {"original_text": "Hey Friday, how are you?", "from_number": ""},
            })

        assert "message" in result
        # System prompt still in Portuguese
        assert "português" in capture.last_system.lower() or "friday" in capture.last_system.lower()

    async def test_zenya_handles_message_with_special_characters(self):
        """Zenya must handle emoji, accents, and special chars without crashing."""
        special_text = "Oi! Quero saber sobre o produto 😊 com acentuação (R$150,00) — teste!"
        capture = CallClaudeCapture("Com certeza!")
        sb = _supabase_with_history([])

        with patch("runtime.tasks.handlers.send_character_message.call_claude", capture), \
             patch("runtime.tasks.handlers.send_character_message.supabase", sb):
            from runtime.tasks.handlers.send_character_message import handle_send_character_message
            result = await handle_send_character_message({
                "id": "ec5",
                "client_id": "client-x",
                "payload": {
                    "character": "zenya",
                    "message": special_text,
                    "phone": "5511000000005",
                    "soul_prompt": "Voce e a Zenya.",
                    "lore": "",
                    "client_name": "X",
                },
            })

        assert "message" in result

    def test_friday_system_prompt_instructs_portuguese(self):
        """Friday's system prompt must explicitly require Portuguese responses."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "português" in lower

    def test_friday_system_prompt_instructs_concise_whatsapp_format(self):
        """Friday is a WhatsApp assistant — prompt must instruct concise responses."""
        from runtime.tasks.handlers.chat import _FRIDAY_SYSTEM_BASE
        lower = _FRIDAY_SYSTEM_BASE.lower()
        assert "whatsapp" in lower
        assert ("concisa" in lower or "curta" in lower or "objetiva" in lower)


class TestFridayIntentClassification:
    """Tests for the dispatcher's classify system prompt integrity."""

    def test_classify_system_prompt_lists_all_intents(self):
        """The classification system prompt must reference every intent in INTENTS."""
        from runtime.friday.dispatcher import _CLASSIFY_SYSTEM, INTENTS
        for intent in INTENTS:
            assert intent in _CLASSIFY_SYSTEM, (
                f"Intent '{intent}' is in INTENTS but not referenced in _CLASSIFY_SYSTEM"
            )

    def test_classify_system_prompt_lists_all_domains(self):
        """The classification system prompt must reference every domain."""
        from runtime.friday.dispatcher import _CLASSIFY_SYSTEM, DOMAINS
        for domain in DOMAINS:
            assert domain in _CLASSIFY_SYSTEM, (
                f"Domain '{domain}' is in DOMAINS but not referenced in _CLASSIFY_SYSTEM"
            )

    def test_classify_system_prompt_instructs_json_output(self):
        """Classification prompt must require JSON output (not markdown or free text)."""
        from runtime.friday.dispatcher import _CLASSIFY_SYSTEM
        assert "json" in _CLASSIFY_SYSTEM.lower()

    def test_classify_system_prompt_does_not_leak_api_keys(self):
        """Classification prompt must never contain API keys or secrets."""
        from runtime.friday.dispatcher import _CLASSIFY_SYSTEM
        lower = _CLASSIFY_SYSTEM.lower()
        assert "api_key" not in lower
        assert "sk-" not in lower
        assert "bearer" not in lower
        assert "password" not in lower


class TestZenyaConversationParsing:
    """Tests for _parse_conversation used in the learn endpoint."""

    def test_parse_standard_format(self):
        """Standard 'Cliente: X / Zenya: Y' format must parse correctly."""
        from runtime.zenya.router import _parse_conversation
        text = "Cliente: Oi, tudo bem?\nZenya: Ola! Tudo otimo, como posso ajudar?"
        result = _parse_conversation(text)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Oi, tudo bem?"}
        assert result[1] == {"role": "assistant", "content": "Ola! Tudo otimo, como posso ajudar?"}

    def test_parse_empty_input(self):
        """Empty text should return empty list, not crash."""
        from runtime.zenya.router import _parse_conversation
        assert _parse_conversation("") == []
        assert _parse_conversation("   \n\n  ") == []

    def test_parse_ignores_unknown_prefixes(self):
        """Lines without recognized prefix are silently ignored."""
        from runtime.zenya.router import _parse_conversation
        text = "random line here\nCliente: Oi\nmore noise\nZenya: Ola"
        result = _parse_conversation(text)
        assert len(result) == 2

    def test_parse_alternative_format(self):
        """user: / assistant: format (runtime native) must also parse."""
        from runtime.zenya.router import _parse_conversation
        text = "user: hello\nassistant: hi there"
        result = _parse_conversation(text)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"


class TestResponder:
    """Tests for the Friday response builder — ensures proper output formatting."""

    def test_build_response_done_with_message(self):
        """Done task with message key returns the message."""
        from runtime.friday.responder import build_response
        task = {"status": "done", "task_type": "chat", "result": {"message": "Tudo certo!"}}
        assert build_response(task) == "Tudo certo!"

    def test_build_response_failed_includes_error(self):
        """Failed task response includes the error."""
        from runtime.friday.responder import build_response
        task = {"status": "failed", "task_type": "chat", "error": "timeout"}
        result = build_response(task)
        assert "timeout" in result
        assert "erro" in result.lower()

    def test_build_response_pending_gives_processing_message(self):
        """Pending/running task gives a 'processing' message."""
        from runtime.friday.responder import build_response
        task = {"status": "pending", "task_type": "chat"}
        result = build_response(task)
        assert "processando" in result.lower()

    def test_build_error_response_truncates(self):
        """Error response should truncate very long exceptions."""
        from runtime.friday.responder import build_error_response
        long_error = "x" * 500
        result = build_error_response(Exception(long_error))
        assert len(result) < 300

    def test_build_response_plain_strips_markdown(self):
        """Plain response builder strips bold/italic/headers for TTS."""
        from runtime.friday.responder import build_response_plain
        task = {
            "status": "done",
            "task_type": "chat",
            "result": {"message": "**Oi** Mauro! _Tudo_ bem?\n# Titulo"},
        }
        result = build_response_plain(task)
        assert "**" not in result
        assert "_" not in result or result.count("_") == 0
        assert "#" not in result

"""
Brain Isolation — B1-03: Per-agent brain access control.

Ensures each agent can only read/write brain data scoped to its own domain:
  - friday       -> brain_owner = "friday"
  - zenya_*      -> brain_owner = client_id (must be provided)
  - system/orion -> brain_owner = None (unrestricted, reads all)
  - default      -> brain_owner = agent_slug

Functions:
  get_brain_owner_filter(agent_slug, client_id) -> str | None
  validate_brain_access(agent_slug, requested_owner, client_id) -> bool
  verify_isolation(agent_a, agent_b) -> dict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Agents with unrestricted (no-filter) access to all brain data
UNRESTRICTED_AGENTS = frozenset({"system", "orion"})

# Agents whose brain_owner is always their own slug (not client-scoped)
SELF_SCOPED_AGENTS = frozenset({"friday", "brain"})

# C2-B1: Named namespaces — valid brain_owner values beyond agent slugs
# and client UUIDs. Used for organizational knowledge domains.
NAMED_NAMESPACES = frozenset({
    "mauro-personal",   # Mauro's strategic vision, decisions, session summaries
    "sparkle-lore",     # Character IP: Zenya lore, SOUL, character bibles
    "sparkle-ops",      # Operational rules: pipeline, feedback, SOP
})


def get_brain_owner_filter(
    agent_slug: str,
    client_id: str | None = None,
) -> str | None:
    """Return the brain_owner value an agent is allowed to access.

    Returns:
        str  — the brain_owner filter to apply (.eq("brain_owner", value))
        None — no filter; agent can read all brain data (system/orion)
    """
    slug = (agent_slug or "").lower().strip()

    # System / Orion — unrestricted
    if slug in UNRESTRICTED_AGENTS:
        return None

    # Friday — always scoped to "friday"
    if slug in SELF_SCOPED_AGENTS:
        return slug

    # Zenya agents (zenya_confeitaria, zenya_ensinaja, etc.) — scoped to client_id
    if slug.startswith("zenya"):
        if not client_id:
            logger.warning(
                "[brain/isolation] zenya agent '%s' called without client_id — "
                "falling back to agent_slug as brain_owner",
                slug,
            )
            return slug
        return client_id

    # Default: agent_slug itself (safe fallback)
    return slug


def validate_brain_access(
    agent_slug: str,
    requested_owner: str,
    client_id: str | None = None,
) -> bool:
    """Check if an agent is allowed to access a specific brain_owner's data.

    Returns True if the agent can access data with brain_owner=requested_owner.
    """
    allowed_owner = get_brain_owner_filter(agent_slug, client_id)

    # Unrestricted agents (system/orion) can access anything
    if allowed_owner is None:
        return True

    # Otherwise, the allowed owner must match exactly
    return allowed_owner == requested_owner


def is_valid_namespace(brain_owner: str) -> bool:
    """Check if a brain_owner value is a recognized named namespace.

    Named namespaces are organizational domains (mauro-personal, sparkle-lore,
    sparkle-ops) that exist beyond agent slugs and client UUIDs.

    Returns True for any value in NAMED_NAMESPACES.
    """
    return brain_owner in NAMED_NAMESPACES


def get_brain_owner_for_ingest(
    agent_slug: str,
    client_id: str | None = None,
    target_namespace: str | None = None,
) -> str:
    """Return the brain_owner value to set when an agent ingests data.

    Unlike get_brain_owner_filter (which returns None for unrestricted agents),
    ingest always requires a concrete brain_owner value.

    System/orion ingests default to "system" so they are explicitly tagged.

    C2-B1: If target_namespace is provided and is a valid named namespace,
    it takes priority. This allows the seed script and auto-ingest to write
    to organizational namespaces (mauro-personal, sparkle-lore, sparkle-ops).
    """
    # C2-B1: explicit namespace override
    if target_namespace and target_namespace in NAMED_NAMESPACES:
        return target_namespace

    slug = (agent_slug or "").lower().strip()

    if slug in UNRESTRICTED_AGENTS:
        return "system"

    owner = get_brain_owner_filter(slug, client_id)
    # Should never be None here since we handled unrestricted above,
    # but defensive coding:
    return owner or slug


def verify_isolation(agent_a: str, agent_b: str) -> dict:
    """Cross-isolation test helper.

    Checks whether agent_a can see agent_b's data and vice-versa.
    Useful for testing and auditing brain isolation boundaries.

    Returns:
        dict with keys:
          - a_can_see_b: bool
          - b_can_see_a: bool
          - a_owner: str | None (what agent_a's brain_owner filter resolves to)
          - b_owner: str | None (what agent_b's brain_owner filter resolves to)
          - isolated: bool (True if neither can see the other's data, unless unrestricted)
    """
    a_owner = get_brain_owner_filter(agent_a)
    b_owner = get_brain_owner_filter(agent_b)

    # For the cross-check, we test if a can access b's owner and vice-versa
    # If b_owner is None (unrestricted), there is no specific "owner" to test against
    if b_owner is not None:
        a_can_see_b = validate_brain_access(agent_a, b_owner)
    else:
        # b is unrestricted — its data is tagged as "system";
        # can agent_a access brain_owner="system"?
        a_can_see_b = validate_brain_access(agent_a, "system")

    if a_owner is not None:
        b_can_see_a = validate_brain_access(agent_b, a_owner)
    else:
        b_can_see_a = validate_brain_access(agent_b, "system")

    # "isolated" = neither can see the other (both restricted, owners differ)
    isolated = not a_can_see_b and not b_can_see_a

    return {
        "a_can_see_b": a_can_see_b,
        "b_can_see_a": b_can_see_a,
        "a_owner": a_owner,
        "b_owner": b_owner,
        "isolated": isolated,
    }

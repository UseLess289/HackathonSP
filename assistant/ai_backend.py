"""AI backend interface (AN-004 / spec §6).

All LLM calls go through `AIBackend`, so the provider can be swapped.
`RuleBackend` is a deterministic offline implementation used for the demo
and the tests: it produces the exact validated JSON contract without any
network or API key, which guarantees demo reliability. A cloud backend can
be plugged in later behind the same interface.
"""

from __future__ import annotations

import abc
import json
from typing import Any

from .models import Action, LLMReply, PersonalData, Profile

# FALC system prompt injected for the simple profile (DEMO-003).
FALC_SYSTEM_PROMPT = (
    "Profil FALC (accompagnement simplifié) : une seule question à la fois, "
    "phrases courtes, vocabulaire usuel, aucun jargon administratif sans "
    "explication, annonce chaque étape importante avant de la faire, et "
    "toujours demander une confirmation explicite avant d'envoyer un email."
)


class AIBackend(abc.ABC):
    """Minimal provider-independent interface."""

    @abc.abstractmethod
    def complete(self, messages: list[dict[str, str]], available_files: list[str],
                 form_fields: dict[str, str], data_so_far: dict[str, str],
                 profile: Profile = Profile.SIMPLE) -> LLMReply:
        """Return a normalized reply (message + validated actions).

        `profile` adapts the prompts/messages sent to the model (DEMO-003):
        the simple (FALC) profile produces one question at a time with short
        sentences; the standard profile uses regular wording.
        """
        ...


class RuleBackend(AIBackend):
    """Deterministic offline backend (demo + tests).

    Mimics the LLM JSON contract (DEMO-011) with fixed rules:
    - if personal data is incomplete -> one ask_question at a time (FALC);
    - else -> fill_form, prepare_email, request_confirmation.
    `send_email` is never produced here: it only happens after explicit
    user confirmation in the orchestrator. Wording adapts to `profile`.
    """

    def complete(self, messages: list[dict[str, str]], available_files: list[str],
                 form_fields: dict[str, str], data_so_far: dict[str, str],
                 profile: Profile = Profile.SIMPLE) -> LLMReply:
        simple = profile == Profile.SIMPLE
        last_user = next((m["content"] for m in reversed(messages)
                          if m.get("role") == "user"), "")
        lower = last_user.lower()

        if any(w in lower for w in ("annul", "stop", "arrête")):
            return LLMReply(message="D'accord, j'annule la démarche.",
                            actions=[Action(type="cancel", message="Démarche annulée.")])

        # A direct answer to a pending question fills the missing field.
        missing = [f for f, v in data_so_far.items() if not str(v).strip()]
        if missing:
            field = missing[0]
            label = form_fields.get(field, field)
            # If the user just answered a question, store the answer.
            if last_user and not lower.startswith(("remplis", "envoie", "prépare")):
                msg = f"Merci, j'ai noté : {last_user}." if simple else f"Valeur enregistrée pour « {label} » : {last_user}"
                return LLMReply(
                    message=msg,
                    actions=[Action(type="fill_form", fields={field: last_user},
                                    message=msg)],
                )
            q = (f"Il me manque une information. Quelle est votre {label.lower()} ?"
                 if simple else f"Champ requis manquant : {label}. Valeur ?")
            return LLMReply(
                message=q,
                actions=[Action(type="ask_question", question=q, message=q)],
            )

        msg = ("J'ai tout ce qu'il faut. Je remplis le formulaire, puis je prépare l'email."
               if simple else
               "Données complètes : remplissage du formulaire puis préparation de l'email.")
        return LLMReply(
            message=msg,
            actions=[
                Action(type="fill_form", fields=dict(data_so_far),
                       message=msg),
                Action(type="prepare_email",
                       message=("Je prépare l'email avec le formulaire en pièce jointe."
                                if simple else "Préparation du brouillon email (pièce jointe : formulaire).")),
                Action(type="request_confirmation",
                       summary="Formulaire rempli, email prêt. Confirmez-vous l'envoi ?",
                       message="Voulez-vous envoyer cet email ?"),
            ],
        )

    # Convenience wrapper matching the spec's JSON format for logging/tests.
    @staticmethod
    def to_contract_json(reply: LLMReply) -> str:
        return json.dumps({
            "message_utilisateur": reply.message,
            "actions": [a.to_dict() for a in reply.actions],
        }, ensure_ascii=False)


class CloudAIBackend(AIBackend):
    """Pluggable cloud backend (stub — configured by env var, never hardcoded).

    Sends only normalized fields (never full PDFs) to the configured
    provider. Not used in the offline demo; kept to honor the AIBackend
    interface from the spec.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key  # never logged, never stored (ZDR)
        self.model = model

    def complete(self, messages: list[dict[str, str]], available_files: list[str],
                 form_fields: dict[str, str], data_so_far: dict[str, str],
                 profile: Profile = Profile.SIMPLE) -> LLMReply:
        import urllib.request

        # DEMO-003: the FALC rules are part of the system prompt for the
        # simple profile; only normalized fields ever leave the machine.
        sys_messages: list[dict[str, str]] = []
        if profile == Profile.SIMPLE:
            sys_messages.append({"role": "system", "content": FALC_SYSTEM_PROMPT})
        payload = {
            "model": self.model,
            "messages": sys_messages + messages,
            "format": "json",
            "available_files": available_files,
            "form_fields": form_fields,
            "data_so_far": data_so_far,
            "profile": profile.value,
        }
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
        return LLMReply.from_json(body["message"]["content"])


def backend_from_env() -> AIBackend:
    """Build a backend from environment variables (AN-013).

    Defaults to the deterministic offline backend so the demo always works.
    Set ASSISTANT_AI_URL / ASSISTANT_AI_KEY / ASSISTANT_AI_MODEL to use cloud.
    """
    import os

    url = os.environ.get("ASSISTANT_AI_URL")
    key = os.environ.get("ASSISTANT_AI_KEY", "")
    model = os.environ.get("ASSISTANT_AI_MODEL", "")
    if url and model:
        return CloudAIBackend(url, key, model)
    return RuleBackend()

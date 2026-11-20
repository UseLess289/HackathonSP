"""Data models for the assistant workflow.

The state machine, the LLM action contract and the personal-data structure
are the safety core of the demo: nothing sensitive is executed or sent
without passing through these validated structures.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


class WorkflowState(str, enum.Enum):
    """States of the demo workflow (DEMO-010)."""

    IDLE = "IDLE"
    UNDERSTANDING_REQUEST = "UNDERSTANDING_REQUEST"
    READING_DOCUMENTS = "READING_DOCUMENTS"
    ASKING_MISSING_DATA = "ASKING_MISSING_DATA"
    FILLING_FORM = "FILLING_FORM"
    PREPARING_EMAIL = "PREPARING_EMAIL"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SENDING = "SENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NEEDS_HELP = "NEEDS_HELP"


class Profile(str, enum.Enum):
    """Accompaniment profiles (DEMO-003).

    `simple` is the FALC profile: one question at a time, short sentences,
    plain words, every important step is announced before it happens.
    `standard` is the default profile for users comfortable with technology.
    """

    SIMPLE = "simple"
    STANDARD = "standard"


class PrivacyMode(str, enum.Enum):
    """What the user is currently told about data processing (DEMO-015)."""

    LOCAL = "local"    # badge "🔒 Traitement 100 % local"
    CLOUD = "cloud"    # badge "☁️ Échange chiffré" (only while the AI is called)
    NEUTRAL = "neutral"


# Allowed action types in the LLM JSON contract (DEMO-011).
ACTION_TYPES = {
    "read_documents",
    "ask_question",
    "fill_form",
    "prepare_email",
    "request_confirmation",
    "send_email",
    "cancel",
}

ActionType = Literal[
    "read_documents",
    "ask_question",
    "fill_form",
    "prepare_email",
    "request_confirmation",
    "send_email",
    "cancel",
]

# Safety caps on model-produced strings (DEMO-011): returned text is data,
# never code — control characters are stripped and lengths are capped so a
# malicious payload cannot smuggle shell commands or huge blobs.
MAX_TEXT_LEN = 500
MAX_FIELDS = 16


def _sanitize(text: Any) -> str:
    """Turn any model-returned value into plain, inert text."""
    s = str(text)
    # Drop control characters (keep printable text, tabs/newlines normalized).
    s = "".join(ch for ch in s if ch.isprintable() or ch in "\n\t")
    s = s.replace("\r", "").strip()
    return s[:MAX_TEXT_LEN]


@dataclass
class Action:
    """One validated action from the LLM (or rule-based backend) contract."""

    type: str
    message: str = ""  # user-facing message (French, simple language)
    question: str = ""  # for ask_question
    fields: dict[str, str] = field(default_factory=dict)  # for fill_form
    summary: str = ""  # for request_confirmation

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        """Validate an LLM-produced action dict. Unknown types are rejected (DEMO-011)."""
        if not isinstance(data, dict):
            raise ValueError("action must be a JSON object")
        atype = data.get("type")
        if atype not in ACTION_TYPES:
            raise ValueError(f"unknown action type: {atype!r}")
        if atype == "ask_question" and not data.get("question"):
            raise ValueError("ask_question requires a 'question' field")
        if atype == "fill_form" and not isinstance(data.get("fields"), dict):
            raise ValueError("fill_form requires a 'fields' object")
        if atype == "send_email":
            raise ValueError("send_email is not a model action: it requires prior "
                             "request_confirmation plus explicit user confirmation")
        raw_fields = data.get("fields") or {}
        if len(raw_fields) > MAX_FIELDS:
            raise ValueError("too many fields in fill_form action")
        fields = {_sanitize(k): _sanitize(v) for k, v in raw_fields.items()}
        return cls(
            type=atype,
            message=_sanitize(data.get("message", "")),
            question=_sanitize(data.get("question", "")),
            fields=fields,
            summary=_sanitize(data.get("summary", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "message": self.message, **(
            {"question": self.question} if self.question else {}
        ), **({"fields": self.fields} if self.fields else {}),
            **({"summary": self.summary} if self.summary else {})}


@dataclass
class LLMReply:
    """Normalized LLM output: a user message plus a list of validated actions."""

    message: str
    actions: list[Action] = field(default_factory=list)

    @classmethod
    def from_json(cls, raw: str) -> "LLMReply":
        data = json.loads(raw)
        msg = _sanitize(data.get("message_utilisateur", data.get("message", "")))
        actions = [Action.from_dict(a) for a in data.get("actions", [])]
        return cls(message=msg, actions=actions)


# Form fields of the demo ODS form (DEMO-007). Values are never invented:
# a missing REQUIRED field blocks the workflow and triggers a question
# (DEMO-008/009). Optional fields (lieu_naissance, telephone) are filled
# when known but never block.
FORM_FIELDS: dict[str, str] = {
    "nom": "Nom",
    "prenom": "Prénom",
    "date_naissance": "Date de naissance",
    "lieu_naissance": "Lieu de naissance",
    "adresse": "Adresse",
    "numero_securite_sociale": "Numéro de sécurité sociale",
    "email": "Email",
    "telephone": "Téléphone",
}

# Target cell of each field in the ODS template (DEMO-007, fixed cells).
FORM_CELLS: dict[str, str] = {
    "nom": "B3",
    "prenom": "B4",
    "date_naissance": "B5",
    "lieu_naissance": "B6",
    "adresse": "B7",
    "numero_securite_sociale": "B8",
    "email": "B9",
    "telephone": "B10",
}

# Fields that MUST be present before the form can be filled (DEMO-008).
REQUIRED_FIELDS: dict[str, str] = {
    k: FORM_FIELDS[k]
    for k in ("nom", "prenom", "date_naissance", "adresse",
              "numero_securite_sociale", "email")
}


@dataclass
class PersonalData:
    """Normalized personal data extracted locally from documents (DEMO-006)."""

    nom: str = ""
    prenom: str = ""
    date_naissance: str = ""
    lieu_naissance: str = ""
    adresse: str = ""
    numero_securite_sociale: str = ""
    email: str = ""
    telephone: str = ""
    sources: dict[str, str] = field(default_factory=dict)  # field -> source document

    def to_form_fields(self) -> dict[str, str]:
        return {
            "nom": self.nom,
            "prenom": self.prenom,
            "date_naissance": self.date_naissance,
            "lieu_naissance": self.lieu_naissance,
            "adresse": self.adresse,
            "numero_securite_sociale": self.numero_securite_sociale,
            "email": self.email,
            "telephone": self.telephone,
        }

    def missing_fields(self) -> list[str]:
        """Only required fields block the workflow (DEMO-008)."""
        fields = self.to_form_fields()
        return [f for f in REQUIRED_FIELDS if not fields[f].strip()]

    def to_safe_dict(self) -> dict[str, str]:
        """Dict for display/logs: the NIR is never shown in full."""
        d = self.to_form_fields()
        nir = d["numero_securite_sociale"]
        if nir:
            d["numero_securite_sociale"] = nir[:1] + "*" * (len(nir) - 1)
        return d


@dataclass
class EmailDraft:
    """A prepared email that is NOT sent yet (DEMO-012)."""

    to: str
    subject: str
    body: str
    form_path: str
    attachments: list[str] = field(default_factory=list)
    # DEMO-013: sending is impossible unless this flag is set explicitly by
    # the orchestrator after the user answered "oui".
    user_confirmed: bool = False

    def recap(self) -> str:
        lines = [
            "Le formulaire est rempli.",
            f"Destinataire : {self.to}",
            f"Objet : {self.subject}",
            f"Pièce jointe principale : {self.form_path}",
        ]
        if self.attachments:
            lines.append("Autres pièces jointes : " + ", ".join(self.attachments))
        lines.append("Voulez-vous envoyer cet email ? (oui / non)")
        return "\n".join(lines)

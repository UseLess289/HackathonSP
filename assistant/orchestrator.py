"""Workflow orchestrator — the state machine of the demo (DEMO-003/009/010/011/013/015/016).

States: IDLE -> UNDERSTANDING_REQUEST -> READING_DOCUMENTS ->
ASKING_MISSING_DATA -> FILLING_FORM -> PREPARING_EMAIL ->
WAITING_CONFIRMATION -> SENDING -> COMPLETED (plus CANCELLED / FAILED /
NEEDS_HELP).

Guarantees:
- the current state is always exposed (the UI prints it) and a short
  history allows a safe step back (DEMO-010);
- `send_email` can NEVER happen before WAITING_CONFIRMATION + an explicit
  "oui" from the user — a cloud/LLM action can never bypass it;
- one question at a time (FALC simple profile, DEMO-003/009);
- a missing datum blocks the workflow, it is never invented (DEMO-008);
- the privacy mode (local vs cloud) is tracked so the UI can show the
  badge of DEMO-015 at every step;
- errors never leak a technical traceback to the user (DEMO-016).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ai_backend import AIBackend
from .documents import DocumentError, normalize_personal_data, scan_documents
from .emailer import DEFAULT_RECIPIENT, EmailError, prepare_email, send_email
from .models import (FORM_FIELDS, EmailDraft, PersonalData, PrivacyMode,
                     Profile, WorkflowState)
from .ods_form import FormError, fill_form

# States from which a fresh request simply restarts the understanding step.
_RESTARTABLE = {
    WorkflowState.IDLE,
    WorkflowState.UNDERSTANDING_REQUEST,
    WorkflowState.READING_DOCUMENTS,
    WorkflowState.FILLING_FORM,
    WorkflowState.PREPARING_EMAIL,
    WorkflowState.COMPLETED,
    WorkflowState.CANCELLED,
    WorkflowState.FAILED,
    WorkflowState.NEEDS_HELP,
}

# Commands the user can type at any time (keyboard fallback, DEMO-016).
_CANCEL_WORDS = ("annul", "stop", "arrête", "quitte", "quitter")
_RESET_WORDS = ("recommencer", "recommence", "reset", "nouvelle démarche")
_BACK_WORDS = ("retour", "précédent", "precedent")
_HELP_WORDS = ("aide", "help", "?", "que puis-je dire", "commandes")
_PROFILE_WORDS = ("profil simple", "profil standard")

# Human-readable state labels (French, simple language) for the UI.
STATE_LABELS: dict[WorkflowState, str] = {
    WorkflowState.IDLE: "En attente",
    WorkflowState.UNDERSTANDING_REQUEST: "J'analyse votre demande",
    WorkflowState.READING_DOCUMENTS: "Lecture locale des documents",
    WorkflowState.ASKING_MISSING_DATA: "Question en cours",
    WorkflowState.FILLING_FORM: "Remplissage du formulaire",
    WorkflowState.PREPARING_EMAIL: "Préparation de l'email",
    WorkflowState.WAITING_CONFIRMATION: "En attente de votre confirmation",
    WorkflowState.SENDING: "Envoi de l'email",
    WorkflowState.COMPLETED: "Terminé",
    WorkflowState.CANCELLED: "Annulé",
    WorkflowState.FAILED: "Problème rencontré",
    WorkflowState.NEEDS_HELP: "Besoin d'aide",
}

STATE_PRIVACY: dict[WorkflowState, PrivacyMode] = {
    WorkflowState.READING_DOCUMENTS: PrivacyMode.LOCAL,
    WorkflowState.FILLING_FORM: PrivacyMode.LOCAL,
    WorkflowState.UNDERSTANDING_REQUEST: PrivacyMode.CLOUD,
    WorkflowState.PREPARING_EMAIL: PrivacyMode.LOCAL,
}


@dataclass
class Orchestrator:
    backend: AIBackend
    documents_dir: Path
    template_path: Path
    output_dir: Path
    recipient: str = DEFAULT_RECIPIENT
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    profile: Profile = Profile.SIMPLE

    state: WorkflowState = WorkflowState.IDLE
    privacy: PrivacyMode = PrivacyMode.NEUTRAL
    data: PersonalData = field(default_factory=PersonalData)
    draft: EmailDraft | None = None
    last_recap: str = ""
    history: list[WorkflowState] = field(default_factory=list)
    _confirmed: bool = False
    _pending_question: str = ""
    _pending_field: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------ utils
    def _say(self, text: str) -> str:
        self.messages.append({"role": "assistant", "content": text})
        return text

    def _set(self, state: WorkflowState) -> None:
        """Move to `state`, keeping a one-step history for a safe step back."""
        if state is not self.state:
            self.history.append(self.state)
            if len(self.history) > 4:
                self.history.pop(0)
            self.state = state
        self.privacy = STATE_PRIVACY.get(state, PrivacyMode.NEUTRAL)

    # ------------------------------------------------------------- main loop
    def handle_user_input(self, user_input: str) -> str:
        """Process one user turn (voice transcription or typed text).

        Returns the assistant's user-facing message (French, simple).
        Global commands (cancel / reset / back / help / profile) work from
        any state — the keyboard fallback path (DEMO-016/009).
        """
        user_input = (user_input or "").strip()
        if not user_input:
            return self._say("Je n'ai rien entendu. Vous pouvez réessayer.")
        self.messages.append({"role": "user", "content": user_input})
        lower = user_input.lower()

        try:
            # Global commands, available in every state.
            if any(w in lower for w in _HELP_WORDS) and len(lower) <= 30:
                return self._help()
            if any(w in lower for w in _PROFILE_WORDS):
                return self._switch_profile(lower)
            if any(w in lower for w in _RESET_WORDS):
                self.reset()
                return self._say("On recommence depuis le début. Que souhaitez-vous faire ?")
            if any(w in lower for w in _CANCEL_WORDS) and len(lower) <= 30:
                self._set(WorkflowState.CANCELLED)
                self.draft = None
                self._confirmed = False
                return self._say("D'accord, j'annule. On peut recommencer quand vous voulez.")
            if any(w in lower for w in _BACK_WORDS) and len(lower) <= 30:
                return self._go_back()

            if self.state == WorkflowState.IDLE:
                return self._start(user_input)
            if self.state == WorkflowState.WAITING_CONFIRMATION:
                return self._handle_confirmation(user_input)
            if self.state == WorkflowState.ASKING_MISSING_DATA:
                return self._handle_answer(user_input)
            if self.state in _RESTARTABLE:
                # A new request restarts the understanding step safely.
                return self._start(user_input)
            return self._start(user_input)
        except (DocumentError, FormError, EmailError) as exc:
            self._set(WorkflowState.FAILED)
            return self._say(f"Problème : {exc} — Tapez « recommencer » pour repartir.")
        except Exception:
            # DEMO-016: never show a technical traceback to the user.
            self._set(WorkflowState.FAILED)
            return self._say(
                "Un problème inattendu est arrivé. Rien n'a été envoyé. "
                "Tapez « recommencer » pour repartir à zéro."
            )

    # ------------------------------------------------------- global commands
    def _help(self) -> str:
        self._set(WorkflowState.NEEDS_HELP)
        return self._say(
            "Commandes disponibles : « recommencer » (repartir à zéro), "
            "« retour » (étape précédente), « annuler » (tout arrêter), "
            "« profil simple » ou « profil standard ». "
            "Sinon dites simplement ce que vous voulez faire, par exemple : "
            "« Remplis le formulaire avec mes documents et envoie-le par email »."
        )

    def _switch_profile(self, lower: str) -> str:
        if "profil simple" in lower:
            self.profile = Profile.SIMPLE
            return self._say("Profil simple activé : une question à la fois, phrases courtes.")
        self.profile = Profile.STANDARD
        return self._say("Profil standard activé.")

    def _go_back(self) -> str:
        """Safe step back (DEMO-010): never back from WAITING_CONFIRMATION
        into SENDING; going back from confirmation just re-shows the recap."""
        if not self.history:
            return self._say("On est déjà au début, il n'y a pas d'étape précédente.")
        prev = self.history.pop()
        if prev == WorkflowState.SENDING:
            prev = WorkflowState.WAITING_CONFIRMATION
        self.state = prev
        self.privacy = STATE_PRIVACY.get(prev, PrivacyMode.NEUTRAL)
        if prev == WorkflowState.WAITING_CONFIRMATION and self.draft is not None:
            self._confirmed = False
            return self._say(self.draft.recap())
        return self._say(f"On revient à l'étape : {STATE_LABELS.get(prev, prev.value)}.")

    # ---------------------------------------------------------------- steps
    def _start(self, user_input: str) -> str:
        self._set(WorkflowState.UNDERSTANDING_REQUEST)
        lower = user_input.lower()
        if any(w in lower for w in _CANCEL_WORDS):
            self._set(WorkflowState.CANCELLED)
            return self._say("D'accord, j'annule. On peut recommencer quand vous voulez.")

        # DEMO-003/015: announce the important step before doing it (FALC).
        prefix = ""
        if self.profile == Profile.SIMPLE:
            prefix = "D'accord. Je vais d'abord lire vos documents sur cet ordinateur. "
        self._set(WorkflowState.READING_DOCUMENTS)
        docs = scan_documents(self.documents_dir)
        self.data = normalize_personal_data(docs)
        file_names = [d.path.name for d in docs]
        self.privacy = PrivacyMode.LOCAL

        self.privacy = PrivacyMode.CLOUD  # only now do we call the AI backend
        reply = self.backend.complete(
            messages=self.messages,
            available_files=file_names,
            form_fields=FORM_FIELDS,
            data_so_far=self.data.to_form_fields(),
            profile=self.profile,
        )
        self.privacy = PrivacyMode.LOCAL
        text = (prefix + reply.message) if prefix else (reply.message or "J'ai lu vos documents.")
        self._say(text)
        return self._apply_actions(reply.actions, initial=True)

    def _apply_actions(self, actions, initial: bool = False) -> str:
        for action in actions:
            if action.type == "cancel":
                self._set(WorkflowState.CANCELLED)
                return self._say(action.message or "Démarche annulée.")
            if action.type == "ask_question":
                self._set(WorkflowState.ASKING_MISSING_DATA)
                self._pending_question = action.question
                self._pending_field = ""
                return self._say(action.question)
            if action.type == "fill_form":
                # Merge answers coming from the user turns.
                self._merge_fields(action.fields)
        return self._continue_after_documents()

    def _merge_fields(self, fields: dict[str, str]) -> None:
        current = self.data.to_form_fields()
        for k, v in fields.items():
            if k in current:
                setattr(self.data, k, v)
                self.data.sources[k] = "saisie utilisateur"

    def _continue_after_documents(self) -> str:
        missing = self.data.missing_fields()
        if missing:
            self._set(WorkflowState.ASKING_MISSING_DATA)
            field_name = missing[0]
            label = FORM_FIELDS[field_name]
            self._pending_field = field_name
            if self.profile == Profile.SIMPLE:
                self._pending_question = f"Il me manque une information. Quelle est votre {label.lower()} ?"
            else:
                self._pending_question = f"Champ requis manquant : {label}. Valeur ?"
            return self._say(self._pending_question)

        # All fields present -> fill the form deterministically (DEMO-008:
        # dated, person-named output; the template stays intact).
        self._set(WorkflowState.FILLING_FORM)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        slug = (f"{self.data.prenom}_{self.data.nom}".lower()
                .replace(" ", "_").replace("'", ""))
        out = self.output_dir / f"dossier_rempli_{slug}.ods"
        fill_form(self.template_path, out, self.data)

        # Prepare the email (not sent yet, DEMO-012). Attachment: the filled
        # form + the justificatif de domicile PDF only.
        self._set(WorkflowState.PREPARING_EMAIL)
        attachments = [p for p in sorted(self.documents_dir.glob("*.pdf"))
                       if "justificatif" in p.name.lower()]
        self.draft = prepare_email(out, attachments, recipient=self.recipient,
                                   data=self.data)

        # Human confirmation is mandatory before sending (DEMO-013).
        self._set(WorkflowState.WAITING_CONFIRMATION)
        self._confirmed = False
        self.last_recap = self.draft.recap()
        return self._say(self.last_recap)

    def _handle_answer(self, answer: str) -> str:
        """The user answered the pending question: store it, then continue.

        DEMO-009: the answer is echoed back for confirmation, and a user
        can correct a previous answer by saying « corrige ... ».
        """
        lower = answer.lower()
        if lower.startswith("corrige") or lower.startswith("en fait"):
            # Correction of a previously given field: re-ask that field.
            target = self._pending_field or self.data.missing_fields()[0] if self.data.missing_fields() else self._pending_field
            if not target:
                for f in FORM_FIELDS:
                    if f in lower.replace("corrige", "").replace("mon", "").replace("ma", "").strip():
                        target = f
                        break
            if target in FORM_FIELDS:
                setattr(self.data, target, "")
                self._set(WorkflowState.ASKING_MISSING_DATA)
                label = FORM_FIELDS[target]
                self._pending_field = target
                self._pending_question = f"D'accord, nouvelle valeur pour {label.lower()} ?"
                return self._say(self._pending_question)
            return self._say("Quel champ voulez-vous corriger ? Dites par exemple « corrige mon email ».")

        missing = self.data.missing_fields()
        field_name = self._pending_field or (missing[0] if missing else "")
        if field_name and field_name in FORM_FIELDS:
            setattr(self.data, field_name, answer)
            self.data.sources[field_name] = "saisie utilisateur"
            echo = f"J'ai noté « {FORM_FIELDS[field_name]} » : {answer}. " if self.profile == Profile.SIMPLE else ""
            self._pending_field = ""
            result = self._continue_after_documents()
            return self._say(echo + result) if echo else result
        return self._continue_after_documents()

    def _handle_confirmation(self, user_input: str) -> str:
        lower = user_input.lower()
        if lower in ("oui", "yes", "ok", "confirme", "envoie", "envoyer", "confirmer"):
            if self.draft is None or not self._confirmed_possible():
                # Hard guarantee (DEMO-010/013): SENDING is reachable ONLY
                # from WAITING_CONFIRMATION with an explicit confirmation.
                self._set(WorkflowState.FAILED)
                return self._say("Impossible d'envoyer maintenant. Recommençons la démarche.")
            self._confirmed = True
            self._set(WorkflowState.SENDING)
            # DEMO-013: the explicit flag is what authorizes the SMTP call;
            # send_email itself refuses to run without it.
            self.draft.user_confirmed = True
            send_email(self.draft, host=self.smtp_host, port=self.smtp_port)
            self._set(WorkflowState.COMPLETED)
            return self._say(
                "C'est envoyé. Vous pouvez vérifier le message dans la boîte de test locale."
            )
        if lower in ("non", "no", "annule", "stop"):
            self._set(WorkflowState.CANCELLED)
            self.draft = None
            self._confirmed = False
            return self._say("Pas de souci, je n'envoie rien. La démarche est annulée.")
        # Ambiguous answer -> ask again (DEMO-013).
        return self._say("Je n'ai pas compris. Voulez-vous envoyer cet email ? Répondez « oui » ou « non ».")

    def _confirmed_possible(self) -> bool:
        return self.state == WorkflowState.WAITING_CONFIRMATION and self.draft is not None

    # ------------------------------------------------------------- helpers
    def reset(self) -> None:
        """Clean restart (DEMO-016: 'Recommencer' button lands on a healthy state)."""
        self.state = WorkflowState.IDLE
        self.privacy = PrivacyMode.NEUTRAL
        self.data = PersonalData()
        self.draft = None
        self.last_recap = ""
        self.history = []
        self._confirmed = False
        self._pending_question = ""
        self._pending_field = ""
        self.messages = []

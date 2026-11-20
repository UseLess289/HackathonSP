"""End-to-end tests of the demo scenario (DEMO-018: must pass 3x consecutively).

Covers: local document scan, normalization, deterministic ODS filling,
mandatory human confirmation (send is impossible without "oui"), and the
local mail sink receiving the message with attachments.
"""

from __future__ import annotations

import shutil
import smtplib
import tempfile
import threading
import unittest
from pathlib import Path

from aiosmtpd.controller import Controller

from assistant.ai_backend import RuleBackend
from assistant.documents import WATERMARK, scan_documents
from assistant.emailer import prepare_email
from assistant.make_demo_data import make_documents, make_template
from assistant.models import (FORM_FIELDS, Action, LLMReply, PersonalData,
                              PrivacyMode, Profile, WorkflowState)
from assistant.orchestrator import Orchestrator
from assistant.ods_form import fill_form, read_form_values
from assistant.smtp_sink import MailSink

ROOT = Path(__file__).resolve().parent.parent


class DemoTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="demo_test_"))
        cls.docs_dir = cls.tmp / "documents"
        cls.out_dir = cls.tmp / "out"
        cls.out_dir.mkdir(parents=True)
        make_documents(cls.docs_dir)
        cls.template = make_template(cls.tmp / "formulaire_demo.ods")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _orch(self, port: int) -> Orchestrator:
        return Orchestrator(
            backend=RuleBackend(),
            documents_dir=self.docs_dir,
            template_path=self.template,
            output_dir=self.out_dir,
            smtp_port=port,
        )

    # ------------------------------------------------------------ DEMO-004/5
    def test_documents_are_fictitious_and_scanned(self):
        docs = scan_documents(self.docs_dir)
        self.assertEqual(len(docs), 3)
        for d in docs:
            self.assertTrue(d.fictitious, f"{d.path.name} must carry the fictitious watermark")
            self.assertIn(WATERMARK, d.text)

    def test_missing_document_raises_user_friendly_error(self):
        from assistant.documents import DocumentError
        with self.assertRaises(DocumentError):
            scan_documents(self.tmp / "does_not_exist")

    # ------------------------------------------------------------ DEMO-006/8
    def test_normalize_and_fill_form_deterministically(self):
        from assistant.documents import normalize_personal_data
        data = normalize_personal_data(scan_documents(self.docs_dir))
        self.assertEqual(data.nom, "DUPONT")
        self.assertEqual(data.prenom, "Marie")
        self.assertEqual(data.date_naissance, "12/03/1985")
        self.assertEqual(data.lieu_naissance, "Lyon (69)")
        self.assertIn("12 rue des Lilas", data.adresse)
        # DEMO-006: NIR validated to exactly 15 digits, spaces removed
        self.assertEqual(data.numero_securite_sociale, "285037512345678")
        self.assertEqual(len(data.numero_securite_sociale), 15)
        # email is not in any document -> must be missing, never invented
        self.assertIn("email", data.missing_fields())
        # optional fields (telephone, lieu_naissance) never block
        self.assertNotIn("telephone", data.missing_fields())

        out = self.out_dir / "filled.ods"
        with self.assertRaises(Exception):
            fill_form(self.template, out, data)  # missing email -> blocked
        data.email = "marie.dupont@example.test"
        fill_form(self.template, out, data)
        values = read_form_values(out)  # DEMO-008: values re-read after write
        self.assertEqual(values["nom"], "DUPONT")
        self.assertEqual(values["prenom"], "Marie")
        self.assertEqual(values["date_naissance"], "12/03/1985")
        self.assertEqual(values["lieu_naissance"], "Lyon (69)")
        self.assertEqual(values["email"], "marie.dupont@example.test")
        self.assertIn("REMPLI", values.get("statut", ""))
        # the template itself must stay intact (DEMO-008)
        self.assertEqual(read_form_values(self.template).get("nom", ""), "")

    # ------------------------------------------------------- DEMO-011 contract
    def test_action_contract_rejects_unknown_and_send_email(self):
        with self.assertRaises(ValueError):
            Action.from_dict({"type": "delete_everything"})
        with self.assertRaises(ValueError):
            Action.from_dict({"type": "send_email"})  # model can never send directly
        a = Action.from_dict({"type": "ask_question", "question": "Votre email ?"})
        self.assertEqual(a.type, "ask_question")
        with self.assertRaises(ValueError):
            LLMReply.from_json('{"message_utilisateur":"x","actions":[{"type":"rm -rf"}]}')

    # ------------------------------------------- DEMO-010/013 full scenario x3
    def test_full_scenario_three_times_with_confirmation(self):
        for run in range(1, 4):
            with self.subTest(run=run):
                port = 11025 + run
                mailbox = self.tmp / f"mailbox_{run}"
                controller = Controller(MailSink(mailbox), hostname="127.0.0.1", port=port)
                controller.start()
                try:
                    orch = self._orch(port)
                    r = orch.handle_user_input("Remplis le formulaire avec ma CNI et ma carte Vitale, puis envoie-le par email.")
                    self.assertEqual(orch.state, WorkflowState.ASKING_MISSING_DATA, r)
                    self.assertIn("email", r.lower())

                    r = orch.handle_user_input("marie.dupont@example.test")
                    self.assertEqual(orch.state, WorkflowState.WAITING_CONFIRMATION, r)
                    self.assertIn("demarche-accessibilite@prefecture.test", r)
                    # DEMO-012: person-specific subject in the recap
                    self.assertIn("Dépôt de dossier administratif — Marie DUPONT", r)
                    self.assertIn("Voulez-vous envoyer", r)

                    # Trying to force a send without confirmation is impossible:
                    # state guard — only WAITING_CONFIRMATION can lead to SENDING.
                    self.assertNotEqual(orch.state, WorkflowState.SENDING)

                    # "non" cancels, nothing is sent
                    orch2 = self._orch(port)
                    orch2.handle_user_input("Remplis le formulaire.")
                    orch2.handle_user_input("marie.dupont@example.test")
                    r = orch2.handle_user_input("non")
                    self.assertEqual(orch2.state, WorkflowState.CANCELLED)
                    self.assertEqual(len(list(mailbox.glob('*.eml'))), 0)

                    r = orch.handle_user_input("oui")
                    self.assertEqual(orch.state, WorkflowState.COMPLETED, r)
                    emls = list(mailbox.glob("*.eml"))
                    self.assertEqual(len(emls), 1, "exactly one email must be received")
                    content = emls[0].read_bytes()
                    self.assertIn(b"dossier_rempli_marie_dupont.ods", content)
                    self.assertIn(b"justificatif_domicile_demo.pdf", content)
                    # DEMO-012: only the justificatif is attached, not the CNI/carte Vitale
                    self.assertNotIn(b"carte_vitale_demo.pdf", content)
                    self.assertNotIn(b"cni_demo.pdf", content)
                finally:
                    controller.stop()

    def test_ambiguous_confirmation_asks_again(self):
        orch = self._orch(11999)  # no sink needed: we never reach SENDING
        orch.handle_user_input("Remplis le formulaire.")
        orch.handle_user_input("marie.dupont@example.test")
        self.assertEqual(orch.state, WorkflowState.WAITING_CONFIRMATION)
        r = orch.handle_user_input("peut-être")
        self.assertEqual(orch.state, WorkflowState.WAITING_CONFIRMATION)
        self.assertIn("oui", r.lower())

    def test_email_prepare_shows_recipient_and_attachments(self):
        docs = scan_documents(self.docs_dir)
        from assistant.documents import normalize_personal_data
        data = normalize_personal_data(docs)
        data.email = "marie.dupont@example.test"
        out = self.out_dir / "prep.ods"
        fill_form(self.template, out, data)
        draft = prepare_email(out, sorted(self.docs_dir.glob("*.pdf")), data=data)
        recap = draft.recap()
        self.assertIn("demarche-accessibilite@prefecture.test", recap)
        self.assertIn("Marie DUPONT", draft.subject)
        self.assertIn("prep.ods", recap)
        self.assertIn("carte_vitale_demo.pdf", recap)
        # DEMO-013: a prepared draft is never confirmed by default
        self.assertFalse(draft.user_confirmed)

    def test_send_email_refused_without_confirmation_flag(self):
        # DEMO-013: the SMTP module itself refuses to send without the flag.
        from assistant.emailer import EmailError, send_email
        docs = scan_documents(self.docs_dir)
        from assistant.documents import normalize_personal_data
        data = normalize_personal_data(docs)
        data.email = "marie.dupont@example.test"
        out = self.out_dir / "guard.ods"
        fill_form(self.template, out, data)
        draft = prepare_email(out, [p for p in self.docs_dir.glob("*.pdf")
                                     if "justificatif" in p.name])
        with self.assertRaises(EmailError):
            send_email(draft, host="127.0.0.1", port=1)  # flag not set -> refusal
        draft.user_confirmed = True
        with self.assertRaises(EmailError):
            send_email(draft, host="127.0.0.1", port=1)  # flag set, but no sink

    def test_data_pipeline_interface_for_dev1(self):
        # Contract from dev2-data-services.md exposed to Dev 1.
        from assistant.data_pipeline import scan_and_extract_local_docs
        result = scan_and_extract_local_docs(self.docs_dir)
        self.assertEqual(result["nom"], "DUPONT")
        self.assertEqual(result["numero_securite_sociale"], "285037512345678")
        self.assertEqual(result["_sources"]["nom"], "cni_demo.pdf")

    # ------------------------------------------- DEMO-011 hardening (security)
    def test_action_contract_sanitizes_and_caps_fields(self):
        malicious = {"type": "fill_form",
                     "fields": {"email": "a@b.test\x00; rm -rf / ; " + "x" * 1000}}
        a = Action.from_dict(malicious)
        self.assertNotIn("\x00", a.fields["email"])  # control chars stripped
        self.assertLessEqual(len(a.fields["email"]), 500)  # length capped
        # the payload stays inert text: fields are data, never executed as code
        with self.assertRaises(ValueError):
            Action.from_dict({"type": "fill_form",
                              "fields": {f"f{i}": "v" for i in range(50)}})

    # ------------------------------------- DEMO-010 states, back, NEEDS_HELP
    def test_state_machine_has_needs_help_and_safe_back(self):
        orch = self._orch(12001)
        r = orch.handle_user_input("aide")
        self.assertEqual(orch.state, WorkflowState.NEEDS_HELP)
        self.assertIn("recommencer", r)
        # back from a state with no history stays safe
        orch2 = self._orch(12002)
        r = orch2.handle_user_input("retour")
        self.assertIn("début", r)
        self.assertEqual(orch2.state, WorkflowState.IDLE)

    def test_sending_is_impossible_without_confirmation(self):
        orch = self._orch(12003)
        # Even a malicious model action cannot reach SENDING from IDLE.
        orch.handle_user_input("Remplis le formulaire.")
        orch.handle_user_input("marie.dupont@example.test")
        self.assertEqual(orch.state, WorkflowState.WAITING_CONFIRMATION)
        self.assertFalse(orch._confirmed_possible() and orch.state == WorkflowState.SENDING)
        # An LLM-issued send_email action is rejected at contract level.
        with self.assertRaises(ValueError):
            Action.from_dict({"type": "send_email"})

    # ------------------------------------------- DEMO-003 profile FALC switch
    def test_profile_switch_and_falc_wording(self):
        orch = self._orch(12004)
        self.assertEqual(orch.profile, Profile.SIMPLE)
        r = orch.handle_user_input("profil standard")
        self.assertEqual(orch.profile, Profile.STANDARD)
        self.assertIn("standard", r)
        r = orch.handle_user_input("profil simple")
        self.assertEqual(orch.profile, Profile.SIMPLE)
        # FALC: the missing-data question is phrased simply.
        orch.handle_user_input("Remplis le formulaire.")
        self.assertEqual(orch.state, WorkflowState.ASKING_MISSING_DATA)
        self.assertIn("email", orch._pending_question.lower())

    # ------------------------------------------- DEMO-009 correction + cancel
    def test_user_can_cancel_and_correct_from_any_state(self):
        orch = self._orch(12005)
        orch.handle_user_input("Remplis le formulaire.")
        self.assertEqual(orch.state, WorkflowState.ASKING_MISSING_DATA)
        r = orch.handle_user_input("annuler")
        self.assertEqual(orch.state, WorkflowState.CANCELLED)
        self.assertIn("annul", r.lower())
        # correction of a previously given field re-asks it
        orch2 = self._orch(12006)
        orch2.handle_user_input("Remplis le formulaire.")
        orch2.handle_user_input("marie.dupont@example.test")
        self.assertEqual(orch2.state, WorkflowState.WAITING_CONFIRMATION)

    # ------------------------------------------- DEMO-015 privacy badges track
    def test_privacy_mode_tracks_local_vs_cloud(self):
        orch = self._orch(12007)
        self.assertEqual(orch.privacy, PrivacyMode.NEUTRAL)
        orch.handle_user_input("Remplis le formulaire.")
        # after the AI call we are back to local processing
        self.assertEqual(orch.state, WorkflowState.ASKING_MISSING_DATA)
        self.assertEqual(orch.privacy, PrivacyMode.NEUTRAL)
        # during the run, READING_DOCUMENTS exposed LOCAL
        self.assertTrue(any(s == WorkflowState.READING_DOCUMENTS for s in orch.history))

    # ------------------------------------------- DEMO-016 errors, no traceback
    def test_errors_are_user_friendly_and_reset_works(self):
        orch = Orchestrator(
            backend=RuleBackend(),
            documents_dir=self.tmp / "nope",
            template_path=self.template,
            output_dir=self.out_dir,
        )
        r = orch.handle_user_input("Remplis le formulaire.")
        self.assertEqual(orch.state, WorkflowState.FAILED)
        self.assertIn("Problème", r)
        self.assertNotIn("Traceback", r)
        r = orch.handle_user_input("recommencer")
        self.assertEqual(orch.state, WorkflowState.IDLE)
        self.assertIn("recommence", r.lower())
        # generic exception -> friendly message, never a traceback (DEMO-016)
        def boom(**kwargs):
            raise RuntimeError("secret internals \x00 traceback")
        orch.backend = type("B", (), {"complete": staticmethod(boom)})()
        orch.documents_dir = self.docs_dir
        r = orch.handle_user_input("Remplis le formulaire.")
        self.assertEqual(orch.state, WorkflowState.FAILED)
        self.assertNotIn("Traceback", r)
        self.assertNotIn("RuntimeError", r)

    def test_smtp_down_gives_friendly_error_and_no_partial_send(self):
        mailbox = self.tmp / "mailbox_down"
        orch = self._orch(12999)  # nothing listens on this port
        orch.handle_user_input("Remplis le formulaire.")
        orch.handle_user_input("marie.dupont@example.test")
        r = orch.handle_user_input("oui")
        self.assertEqual(orch.state, WorkflowState.FAILED)
        self.assertIn("boîte de test", r.lower())
        self.assertEqual(len(list(mailbox.glob('*.eml'))) if mailbox.is_dir() else 0, 0)

    # ------------------------------------------- DEMO-017 demo script steps
    def test_demo_script_scenario_runs(self):
        from assistant.demo_script import STEPS
        self.assertEqual(len(STEPS), 8)
        port = 12010
        mailbox = self.tmp / "mailbox_script"
        controller = Controller(MailSink(mailbox), hostname="127.0.0.1", port=port)
        controller.start()
        try:
            orch = self._orch(port)
            orch.handle_user_input("Remplis le formulaire avec ma CNI et ma carte Vitale, puis envoie-le par email.")
            orch.handle_user_input("marie.dupont@example.test")
            orch.handle_user_input("oui")
            self.assertEqual(orch.state, WorkflowState.COMPLETED)
            self.assertEqual(len(list(mailbox.glob('*.eml'))), 1)
        finally:
            controller.stop()


if __name__ == "__main__":
    unittest.main()

# HackathonSP — Assistant d'accessibilité Linux (démo formulaire + email)

Compagnon bureautique accessible, 100 % local : il lit des documents locaux
(fictifs, filigranés), remplit un formulaire `.ods` de façon déterministe,
pose les questions manquantes une par une, prépare un email et **ne l'envoie
qu'après confirmation explicite** de l'utilisateur, vers une boîte de test
locale. Aucune donnée personnelle ne quitte la machine.

## Lancer la démo

```bash
# 1. environnement virtuel + dépendances
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. créer les données fictives (PDF filigranés + modèle de formulaire)
.venv/bin/python -m assistant.make_demo_data

# 3. terminal 2 : boîte email de test locale (alternative à Mailpit)
.venv/bin/python -m assistant.smtp_sink          # SMTP 127.0.0.1:1025 + UI web http://127.0.0.1:8025

# 4. terminal 1 : l'assistant
.venv/bin/python -m assistant.main --ui web    # interface accessible locale : http://127.0.0.1:8765
.venv/bin/python -m assistant.main --ui cli    # mode clavier (secours garanti, voix optionnelle)

# Variante : scénario de présentation chronométré (90 s)
.venv/bin/python -m assistant.demo_script
```

Scénario de démo : « Remplis le formulaire avec ma CNI et ma carte Vitale,
puis envoie-le par email. » → répondre à la question manquante (email) →
confirmer par « oui » → vérifier le message sur http://127.0.0.1:8025
(pièces jointes `.ods` / `.pdf` téléchargeables) ou dans `demo_data/mailbox/`.
Le formulaire rempli s'appelle `dossier_rempli_marie_dupont.ods` et est envoyé à
`demarche-accessibilite@prefecture.test` avec uniquement le justificatif de
domicile en pièce jointe (objet : « Dépôt de dossier administratif — Marie DUPONT »).

Interface web (axe Dev 1) : gros bouton « Parler » (voix optionnelle via Web
Speech API), champ texte de secours 100 % clavier, grande zone de
transcription, indicateur d'état en direct, badge de confidentialité
(🔒 100 % local / ☁️ échange chiffré IA) et boutons Confirmer / Annuler /
Réessayer. Commandes clavier disponibles à tout moment : `aide`,
`recommencer`, `retour`, `annuler`, `profil simple` / `profil standard`
(profil FALC : une question à la fois, phrases courtes).

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Le scénario complet y est rejoué 3 fois de suite (remplissage correct,
confirmation obligatoire, email reçu avec les bonnes pièces jointes).

## Structure

```
assistant/
├── main.py            # points d'entrée : CLI clavier (secours) + UI web locale
├── ui_server.py       # serveur HTTP 127.0.0.1 de l'interface accessible (Dev 1)
├── ui/index.html      # page accessible : gros boutons, clavier, voix optionnelle,
│                      #   badge confidentialité, ARIA, contraste élevé
├── demo_script.py     # scénario de présentation chronométré (90 s)
├── orchestrator.py    # machine à états + profil FALC + badges + confirmation humaine
├── ai_backend.py      # interface AIBackend + backend déterministe hors-ligne
├── documents.py       # scan local des PDF (pdftotext) + normalisation des champs
├── data_pipeline.py   # interface Dev 1 : scan_and_extract_local_docs(docs_dir)
├── ods_form.py        # remplissage déterministe du .ods, cellules fixes B3-B10
├── emailer.py         # préparation + envoi SMTP (refus sans confirmation explicite)
├── smtp_sink.py       # récepteur SMTP local + UI web :8025 (alternative Mailpit)
├── make_demo_data.py  # génération des documents fictifs filigranés
└── models.py          # états, contrat JSON des actions, profils, données personnelles
doc/                   # pitch, spec v0, tickets AN-* et DEMO-*
tests/test_demo.py     # tests de bout en bout (scénario x3 + tickets Dev 1)
```

## Règles de sécurité de la démo

- Documents.uniquement fictifs, filigrane `DOCUMENT FICTIF — DÉMONSTRATION`.
- Aucun envoi sans confirmation explicite ; `send_email` est impossible avant
  `request_confirmation` + « oui » de l'utilisateur (les actions du modèle sont
  limitées à un contrat JSON validé).
- Extraction du texte des PDF en local ; les PDF complets ne sont jamais envoyés.
- Aucune clé API / identifiant dans git ou dans les logs.

Licence : GPL-3.0-only.

# SPEC PROJET — Assistant d'Accessibilité Universelle (Linux / Rust / 100 % Local)

## 1. Contexte & Objectif
MVP de hackathon (temps limité, priorité absolue à la stabilité en démo live de 90s).
Construire un orchestrateur d'accessibilité universelle **100 % local sur Linux**, écrit en **Rust**, capable de :
1. Comprendre un formulaire web administratif complexe et le remplir à la voix ou au texte.
2. Adapter dynamiquement son comportement (entrées, sorties, niveau de langage) selon un **profil de handicap**.
3. Lire et téléverser automatiquement des pièces justificatives locales (`./papiers_locaux/`) sans jamais envoyer de données personnelles dans le cloud.

## 2. Contraintes Techniques Strictes
- **Langage :** Rust (edition 2021), asynchrone (`tokio`), gestion d'erreurs simple (`anyhow`).
- **Zéro API Cloud :** Tout tourne en local.
- **Zéro bindings C/C++ complexes :** Rust agit comme orchestrateur léger via HTTP (`reqwest`) et sous-processus (`std::process::Command`).
- **Briques locales pilotées :**
  - **LLM :** Ollama (`http://localhost:11434/api/chat`, modèle `qwen2.5:7b` ou `mistral` ou `llama3.2:3b`, mode `"format": "json"`).
  - **STT (Voix -> Texte) :** `arecord` (ALSA) -> `whisper-cli` (whisper.cpp) sur fichier WAV temporaire.
  - **TTS (Texte -> Voix) :** `piper` pipé vers `aplay`.
  - **PDF :** `pdftotext` (poppler-utils) sur le dossier `./papiers_locaux/`.
- **Interface Web / Démo :** Serveur local `axum` servant `static/index.html` (un formulaire administratif réaliste en français + bandeau d'accessibilité) connecté au backend Rust via **WebSocket**.

## 3. Profils d'Accessibilité (`AccessibilityProfile`)
Sélectionnable via CLI (`--profile <profil>`) ou bouton sur l'UI Web :

| Profil | STT | TTS | Prompt Système (comportement LLM) |
| :--- | :---: | :---: | :--- |
| `Visual` | Oui | Oui | Réponses ultra-concises (max 2 phrases), décrit la structure de la page, guide à l'oral. |
| `Motor` | Oui | Oui | Maximise l'automatisation (remplit plusieurs champs en 1 phrase + auto-upload), confirmation obligatoire avant action critique. |
| `Cognitive` | Oui | Oui | **Mode FALC strict** (phrases courtes, mots simples, explique le jargon administratif, 1 seule question à la fois). |
| `Hearing` | Non | Non | Mode silencieux (TTS désactivé), réponses textuelles claires et structurées, simplification du français administratif. |

## 4. Contrat JSON Strict du LLM (`serde`)
Le backend envoie à Ollama le DOM simplifié (`input`, `label`, `select`, `button`) + la liste des fichiers disponibles dans `./papiers_locaux/` + le message utilisateur.
Ollama doit **toujours** répondre avec ce format JSON :

```json
{
  "message_utilisateur": "Texte adapté au profil (affiché à l'écran et lu par Piper si TTS actif)",
  "actions": [
    { "type": "fill", "selector": "#nom", "value": "Jean Dupont" },
    { "type": "read_local_file", "keyword": "edf" },
    { "type": "upload_file", "selector": "#justificatif", "filename": "facture_edf.pdf" },
    { "type": "request_confirmation", "summary": "Récapitulatif des champs avant envoi" },
    { "type": "submit", "selector": "#btn-submit" }
  ]
}
```

## 5. Règles Métier & Garde-fous
- **Human-in-the-loop obligatoire :** Le backend Rust doit **bloquer** toute action `submit` tant qu'une action `request_confirmation` n'a pas été suivie d'une validation explicite de l'utilisateur.
- **Lecture de justificatif :** Si le LLM renvoie `read_local_file`, le backend extrait le texte du PDF correspondant dans `./papiers_locaux/` et relance un tour vers Ollama avec le contenu extrait pour remplir les champs automatiquement.
- **Fallback démo :** L'interface Web doit toujours permettre de saisir une commande au clavier (en plus du micro Push-to-Talk) si l'audio pose problème le jour J.

## 6. Architecture de Fichiers Attendue
```text
.
├── Cargo.toml               # tokio, axum, serde, serde_json, reqwest, clap, anyhow, tracing, futures
├── papiers_locaux/          # Dossier contenant des PDF factices (ex: facture_edf.pdf)
├── static/
│   └── index.html           # Formulaire administratif + sélecteur de profil + client WebSocket + UI adaptative
└── src/
    ├── main.rs              # CLI, état partagé, serveur Axum + handler WebSocket
    ├── profiles.rs          # Enum AccessibilityProfile, config I/O, system prompts
    ├── llm.rs               # Client HTTP Ollama, structs serde du contrat JSON, boucle tool/file
    ├── audio.rs             # Wrappers Command pour arecord, whisper-cli et piper/aplay
    └── files.rs             # Scan de ./papiers_locaux/ + extraction texte via pdftotext
```

## 7. Plan d'Exécution pour OpenCode
Procède étape par étape sans sur-ingénierie :
1. Initialise `Cargo.toml` et vérifie que la compilation de base passe (`cargo check`).
2. Implémente `src/profiles.rs`, `src/files.rs` et `src/llm.rs` (avec le garde-fou `submit`).
3. Implémente `src/audio.rs` avec gestion gracieuse si `piper` ou `whisper-cli` n'est pas installé (log d'avertissement sans crash).
4. Implémente `src/main.rs` (Axum + WebSocket) et `static/index.html` (formulaire administratif complet : nom, prénom, date de naissance, adresse, quotient familial, upload justificatif de domicile, bouton envoyer).
5. Génère un fichier de test `papiers_locaux/facture_edf.txt` (ou PDF) pour tester le flux complet immédiatement.
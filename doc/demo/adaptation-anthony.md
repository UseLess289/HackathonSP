# Démo — Tickets d'adaptation d'Anthony

Ce document concerne uniquement l'adaptation technique d'Anthony pour fournir un moteur local d'interaction avec GNOME et utiliser l'IA cloud.

## Objectif

Obtenir un moteur capable de :

- recevoir une demande vocale ou textuelle ;
- utiliser une IA cloud pour la transcription et la compréhension ;
- consulter l'écran si nécessaire ;
- appeler des outils contrôlés ;
- agir sur GNOME via `anthony-mcp` ;
- retourner un résultat exploitable par notre application.

Le produit d'accessibilité et le scénario formulaire/email sont décrits dans `produit-demo.md`.

## Environnement cible

- Fedora ou distribution RPM compatible ;
- GNOME 45–50 ;
- session Wayland ;
- Python 3.12+ ;
- microphone et haut-parleurs ;
- connexion Internet ;
- aucun GPU dédié requis après suppression de l'inférence locale.

## Tickets

### AN-001 — Créer une branche dédiée à l'adaptation

- **Priorité :** Bloquante
- **Dépendances :** aucune

Créer une branche ou un répertoire de travail séparé pour adapter Anthony sans perdre la version originale.

**Critères d'acceptation :**

- la version originale d'Anthony peut toujours être lancée ;
- les modifications de notre projet sont identifiables ;
- l'autorisation écrite de l'auteur est conservée dans la documentation interne ;
- les mentions d'auteur sont conservées.

### AN-002 — Auditer les composants réutilisés

- **Priorité :** Haute
- **Dépendances :** AN-001

Lister les fichiers Anthony et `anthony-mcp` réellement utilisés par la démo, ainsi que leurs dépendances et licences.

**Critères d'acceptation :**

- les composants réutilisés sont listés ;
- la GPL-3.0 de `anthony-mcp` est documentée ;
- les dépendances et modèles supprimés sont distingués des composants conservés ;
- un fichier d'attributions pourra être fourni avec la démo.

### AN-003 — Installer et valider GNOME/MCP

- **Priorité :** Bloquante
- **Dépendances :** AN-001

Installer l'environnement GNOME, l'extension Anthony et le serveur `anthony-mcp`.

**Critères d'acceptation :**

- `anthony-mcp` démarre correctement ;
- l'extension GNOME est active ;
- un test de santé répond positivement ;
- une capture d'écran peut être récupérée ;
- une fenêtre peut être ouverte et ciblée ;
- du texte peut être saisi dans une application de test.

### AN-004 — Définir l'interface `AIBackend`

- **Priorité :** Bloquante
- **Dépendances :** AN-001

Isoler les appels d'intelligence artificielle derrière une interface indépendante du fournisseur.

Interface minimale prévue :

```python
class AIBackend:
    def transcribe(self, audio): ...
    def complete(self, messages, tools): ...
    def analyze_image(self, image): ...
    def synthesize(self, text): ...
```

**Critères d'acceptation :**

- `llm_chain.py` ne dépend plus directement de `llama-server` ;
- l'implémentation cloud peut être remplacée par une implémentation locale ;
- les formats d'entrée et de sortie sont documentés.

### AN-005 — Remplacer la transcription locale

- **Priorité :** Haute
- **Dépendances :** AN-004

Remplacer `faster-whisper` par une API speech-to-text cloud.

Pour la première démo, utiliser le mode push-to-talk afin d'éviter de devoir finaliser un VAD continu.

**Critères d'acceptation :**

- un enregistrement audio est transmis à l'API ;
- le texte transcrit est retourné ;
- les erreurs réseau sont affichées clairement ;
- le texte vide ou incompréhensible est traité sans exécuter d'action ;
- les fichiers audio temporaires sont supprimés.

### AN-006 — Remplacer le LLM local par un LLM cloud

- **Priorité :** Bloquante
- **Dépendances :** AN-004

Remplacer Gemma/`llama-server` par un modèle cloud capable de comprendre les messages et d'appeler des outils.

**Critères d'acceptation :**

- les messages Anthony sont convertis au format du fournisseur ;
- les outils sont transmis au modèle ;
- les tool calls sont normalisés dans un format interne ;
- une réponse textuelle est gérée ;
- une réponse invalide ne déclenche aucune action ;
- le fournisseur est configuré par variable d'environnement et jamais écrit en dur.

### AN-007 — Ajouter la vision cloud à la demande

- **Priorité :** Haute
- **Dépendances :** AN-006, AN-003

Permettre l'envoi ponctuel d'une capture d'écran à un modèle vision.

**Critères d'acceptation :**

- aucune capture n'est envoyée sans demande ou nécessité identifiée ;
- l'interface indique qu'une capture est envoyée ;
- la taille et le format de l'image sont limités ;
- la réponse de vision peut être utilisée par la boucle de décision ;
- la capture temporaire est supprimée après usage.

### AN-008 — Remplacer Piper par le TTS cloud avec fallback

- **Priorité :** Moyenne
- **Dépendances :** AN-004

Remplacer Piper pour la version cloud, tout en gardant un fallback local pour la démo si l'API TTS échoue.

**Critères d'acceptation :**

- une réponse peut être lue à voix haute ;
- le texte reste toujours visible à l'écran ;
- les réponses vides ou trop longues sont nettoyées ;
- une erreur audio n'interrompt pas le workflow.

### AN-009 — Supprimer la dépendance de démarrage à `llama-server`

- **Priorité :** Haute
- **Dépendances :** AN-006

Retirer du démarrage d'Anthony :

- détection de GPU ;
- recherche de modèles GGUF ;
- démarrage de `llama-server` ;
- warmup des modèles locaux ;
- téléchargement automatique des modèles locaux.

**Critères d'acceptation :**

- l'application démarre sans modèle local ;
- l'absence de GPU ne provoque aucune erreur ;
- aucun fichier de plusieurs gigaoctets n'est nécessaire ;
- seul le réseau et la clé API sont requis pour l'IA.

### AN-010 — Conserver le client MCP local

- **Priorité :** Bloquante
- **Dépendances :** AN-003

Conserver ou adapter le client MCP pour que les appels d'outils restent exécutés localement.

**Critères d'acceptation :**

- le LLM ne peut appeler que les outils autorisés ;
- les résultats MCP sont convertis en texte et/ou données structurées ;
- les timeouts sont gérés ;
- une perte de connexion à MCP n'entraîne pas de fausse réussite.

### AN-011 — Réduire et sécuriser les outils exposés

- **Priorité :** Bloquante
- **Dépendances :** AN-010

N'exposer pour la démo que les outils nécessaires :

- capture d'écran ;
- ouverture/focus de Firefox ;
- saisie de texte ;
- clic contrôlé ;
- sélection de fichier ;
- lecture de l'état de la fenêtre.

Ne pas exposer de shell arbitraire, de suppression de fichiers ou d'arrêt système.

**Critères d'acceptation :**

- une liste blanche d'outils est appliquée côté application ;
- les appels inconnus sont refusés ;
- les actions critiques nécessitent un jeton de confirmation fourni par le workflow produit.

### AN-012 — Normaliser les erreurs d'interaction

- **Priorité :** Haute
- **Dépendances :** AN-010

Créer des erreurs internes explicites :

- `McpUnavailable` ;
- `WindowNotFound` ;
- `ActionRejected` ;
- `ActionTimeout` ;
- `CloudUnavailable` ;
- `InvalidModelResponse`.

**Critères d'acceptation :**

- chaque erreur possède un message utilisateur simple ;
- aucune erreur technique brute n'est lue à l'utilisateur ;
- une action échouée n'est jamais annoncée comme terminée.

### AN-013 — Ajouter la configuration cloud

- **Priorité :** Haute
- **Dépendances :** AN-006

Ajouter une configuration locale pour :

- fournisseur ;
- clé API ;
- modèles utilisés ;
- limites de taille ;
- mode debug.

**Critères d'acceptation :**

- la clé API est lue depuis l'environnement ou un fichier local ignoré par Git ;
- aucune clé n'apparaît dans les logs ;
- l'application vérifie la configuration au démarrage.

### AN-014 — Tester le parcours technique minimal

- **Priorité :** Bloquante
- **Dépendances :** AN-005, AN-006, AN-010, AN-011

Valider le parcours suivant avant de développer le produit :

```text
voix → transcription cloud → appel d'un outil → action GNOME → résultat → réponse vocale
```

**Critères d'acceptation :**

- le parcours fonctionne trois fois consécutivement ;
- un échec réseau est correctement affiché ;
- une action non autorisée est refusée ;
- le texte et la voix retournent le même résultat.

### AN-015 — Préparer le lancement de la démo

- **Priorité :** Haute
- **Dépendances :** AN-014

Créer une commande ou un script unique pour lancer le moteur adapté.

**Critères d'acceptation :**

- l'environnement nécessaire est documenté ;
- les services indispensables sont vérifiés au démarrage ;
- l'utilisateur sait comment arrêter le contrôle automatique ;
- un mode texte de secours existe.

## Résultat attendu de cette partie

Anthony adapté est considéré comme terminé lorsque l'application peut recevoir une demande, appeler un outil MCP autorisé, agir sur GNOME et retourner un résultat fiable, sans aucune inférence locale obligatoire.

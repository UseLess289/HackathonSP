# Plan projet — Compagnon Linux bureautique accessible (ZDR, open source)

**Contexte** : accompagner les entreprises françaises dans leur migration Windows → Linux.
**Produit** : compagnon open source qui aide les employés à réaliser leurs tâches bureautiques
habituelles sur des logiciels libres (ex. Microsoft Office → LibreOffice).
**Premier public** : personnes en situation de handicap (malvoyants, amputés des bras,
malentendants...), puis ouvert à tous les employés.
**Différenciation** : gratuit et libre (contre payant sur Windows), 100% web, ZDR (zéro rétention
de données), aucun matériel lourd requis (contre des solutions client lourdes qui stockent des données).
**Brique clé** : reprendre l'idée d'[anthony-mcp](https://github.com/g0dd4rd/anthony-mcp)
(automatisation du bureau GNOME Wayland via MCP + D-Bus), mais avec une IA fournie par
l'utilisateur via sa propre clé API (BYOK).

## Architecture

```
Navigateur (UI React, clé API stockée uniquement en localStorage)
   │  HTTP vers 127.0.0.1 (clé envoyée uniquement au proxy local)
   ▼
Proxy LLM du serveur MCP local (Python, écoute UNIQUEMENT sur 127.0.0.1,
  relaie vers le fournisseur d'IA choisi, ne logue ni ne stocke jamais la clé ni les prompts)
   │  D-Bus
   ▼
Extension GNOME Shell (Wayland) : screenshots, fenêtres, clavier/souris, réglages accessibilité
   │
   ▼
Applications cibles : LibreOffice, Firefox, Thunderbird...
```

- **ZDR garanti** : la clé API ne quitte jamais la machine de l'employé. Elle transite uniquement
  navigateur → proxy `127.0.0.1` → fournisseur d'IA choisi par l'utilisateur. Aucun serveur tiers
  ne la voit, le proxy ne la journalise ni ne la stocke. La web app est servie en local.
- **Cible desktop** : GNOME Wayland uniquement.
- **Double mode d'interaction** (selon le handicap) :
  - malvoyant / amputé des bras → communication par la voix (Web Speech API : dictée + synthèse, gratuites, intégrées au navigateur) ;
  - mal entendant → communication par texte (chat).
- **Accessibilité active** : UI conforme ARIA, navigation clavier complète, focus visible,
  thèmes haut contraste / grands caractères réglables ; le compagnon sait aussi piloter les
  réglages d'accessibilité de GNOME (Orca, loupe, contraste élevé) via D-Bus et guider la
  création de documents accessibles (ex. Word → ODT avec titres structurés, textes alternatifs).
- **Stack** : UI en React (Vite), serveur MCP local en Python.
- **Licence** : GPL-3.0 (réutilisation du code GPL-3.0 d'anthony-mcp).

## Appel au LLM : proxy local obligatoire (choix retenu)

Le navigateur bloque les appels directs vers la plupart des API (CORS). On retient donc
**l'option 2 : un proxy LLM embarqué dans le serveur MCP local** :

- Le navigateur envoie la requête (prompt + clé API) à `http://127.0.0.1:<port>/llm`.
- Le proxy relaie vers le fournisseur choisi par l'utilisateur (OpenAI, Anthropic, Mistral,
  Ollama local `http://localhost:11434`, etc.) et renvoie la réponse au navigateur.
- **Garanties ZDR du proxy** : écoute uniquement sur `127.0.0.1` (jamais sur le réseau),
  aucune journalisation de la clé, des prompts ni des réponses, aucun stockage sur disque,
  la clé est transmise uniquement au fournisseur d'IA choisi et n'est jamais conservée.
- Avantage : un seul mécanisme qui marche avec **tous** les fournisseurs, y compris ceux qui
  interdisent les appels navigateur. Pour la démo 17h : Mistral (français, bon en français) ou
  Ollama local (100% hors ligne).

## Périmètre bureautique

Liste établie progressivement, priorités de départ : LibreOffice (Writer, Calc, Impress),
Firefox, Thunderbird. Mini base de connaissances « équivalences Windows → Linux ».

## Plan horaire (démo à 17h, il est ~15h)

- Cloner anthony-mcp, installer l'extension GNOME + serveur MCP Python, vérifier `ping` et un screenshot via D-Bus |
- Web app React servie en local : chat, écran de config de la clé API, connexion au MCP local |
- Accessibilité : ARIA + navigation clavier, haut contraste / grands caractères, mode vocal (Web Speech API) |
- Deux scénarios de démo + fiches « équivalences Windows → Linux » (Writer, Calc) |
- Répétition de la démo, README (promesse ZDR, licence GPL-3.0) |

## Scénarios de démo

1. **Mode vocal (malvoyant)** : dictée « crée un document Writer accessible avec un titre et deux paragraphes ».
2. **Mode texte (mal entendant)** : « l'équivalent de SOMME.SI.ENS dans Calc ? » avec démo guidée pas à pas.

## Prérequis / point de vigilance

L'extension anthony-mcp exige une session GNOME Wayland ouverte sur la machine de démo.
Plan B si environnement headless : démo sur enregistrement d'écran ou mode simulation.

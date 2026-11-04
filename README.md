# facebook_agent

Technologies : Python 3.12 · Graph API v23.0 · Groq (gpt-oss-120b, gpt-oss-20b) · Streamlit

> **In short (English).** A Python library and an AI agent that manage a Facebook Page, its product
> catalog, its Lead Ads forms and sandbox ad campaigns through the Graph API v23.0. The 67 operations
> are documented by structured docstrings, from which the LLM tools are generated automatically. The
> agent (Groq, gpt-oss-120b, native function calling) picks the operations, shows every write and waits
> for your confirmation. It runs in a terminal or in a local web interface (Streamlit).

![Comment fonctionne l'agent](docs/images/architecture.png)

https://github.com/user-attachments/assets/040a89fb-af18-4619-85dd-04d46269be49

## Sommaire

- [Présentation](#présentation)
- [Fonctionnalités par domaine](#fonctionnalités-par-domaine)
- [Interface web](#interface-web)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [Sécurité](#sécurité)
- [Architecture](#architecture)
- [Limites](#limites)
- [Contexte](#contexte)

## Présentation

`facebook_agent` réunit trois choses :

1. **Une bibliothèque de 67 opérations** sur la Graph API v23.0 : une fonction Python par action
   (`create_post`, `update_product`, `list_lead_forms`…). Chaque opération valide ses paramètres avant
   d'envoyer quoi que ce soit, renvoie toujours le même format et ne lève jamais d'exception :

   ```python
   {"status": "success", "data": ...}
   {"status": "error", "message": "<message en français>", "details": {"type": "...", ...}}
   ```

2. **Un agent IA** : on lui écrit une demande en français (« Mets le T-shirt Nova en promotion à 12 DT »).
   Il choisit les opérations, montre chaque écriture, attend la confirmation et répond en français. Ses
   outils sont **générés depuis les docstrings** des opérations : aucun schéma n'est écrit à la main.
3. **Trois façons de s'en servir** : un menu interactif pour essayer chaque opération, l'agent en
   terminal, et une interface web locale avec des cartes visuelles.

## Fonctionnalités par domaine

| Domaine | Opérations |
|---|---|
| Authentification (1) | `authenticate` : pages gérées et leurs tokens de page, avec un token court ou échangé contre un token longue durée |
| Posts (10) | `create_post`, `update_post`, `delete_post`, `get_post`, `list_posts`, `list_scheduled_posts`, `create_scheduled_photos_post`, `like_post`, `unlike_post`, `get_post_reactions` |
| Commentaires (6) | `create_comment`, `reply_to_comment`, `list_comments`, `hide_comment`, `unhide_comment`, `delete_comment` |
| Messenger (6) | `list_conversations`, `list_conversation_messages`, `mark_conversation_read`, `send_text_message`, `send_quick_replies`, `send_attachment_from_conversation` |
| Page (1) | `get_page_info` |
| Photos (7) | `upload_photo`, `upload_photo_to_album`, `list_photos`, `list_albums`, `update_cover_photo` et `update_profile_picture` (URL ou fichier local, sans publication dans le fil), `delete_photo` |
| Vidéos (3) | `upload_video` (publication immédiate ou programmée), `list_videos`, `delete_video` |
| Utilisateurs (2) | `ban_user`, `unban_user` |
| Catalogue : produits (4) | `create_product`, `update_product` (prix, promotion, retrait de promotion), `delete_product`, `search_products` |
| Catalogue : collections (4) | `create_product_set`, `update_product_set`, `list_product_sets`, `delete_product_set` |
| Catalogue : flux (4) | `create_and_upload_feed`, `reupload_product_feed`, `list_product_feeds`, `delete_product_feed` |
| Lead Ads (7) | `list_lead_forms`, `create_lead_form`, `archive_lead_form`, `create_test_lead`, `list_test_leads`, `delete_test_lead`, `list_form_leads` |
| Campagnes (12) | `list_campaigns`, `create_campaign`, `update_campaign`, `delete_campaign`, `list_ad_sets`, `create_ad_set`, `update_ad_set`, `delete_ad_set`, `list_ads`, `create_ad`, `update_ad`, `delete_ad` : sur un compte **sandbox** |

Points communs :

- **Validation avant toute requête** : paramètres obligatoires, fenêtres de programmation documentées par
  Meta (post : 10 minutes à 75 jours ; vidéo : 10 minutes à 6 mois), clés de produit acceptées, prix (virgule
  acceptée, envoi en centimes), fichiers locaux existants, formats de flux (CSV, XML, XLSX).
- **Fichier local ou URL** : une valeur qui commence par `http://` ou `https://` est envoyée comme URL ;
  toute autre valeur doit être un fichier local existant.
- **Pagination** : les fonctions `list_*` renvoient la première page, ou toutes les pages avec
  `all_pages=True` (50 pages au plus, signalé par `"truncated": true`).
- **Exemples réels** : le bloc `Example (success)` de chaque docstring montre une vraie réponse de l'API,
  anonymisée.

## Interface web

L'agent dans une page locale : mêmes outils, mêmes contrôles, même journal. Seules changent la
confirmation (boutons), l'affichage (chat et cartes) et l'annulation (bouton).

### Galerie

#### Démarrage et réglages

**Écran de démarrage, en clair et en sombre**

<p>
  <img src="docs/images/demarrage.png" width="49%">
  <img src="docs/images/demarrage-sombre.png" width="49%">
</p>

**Suggestions par domaine, et menu ⋮ avec le passage en mode dry-run**

<p>
  <img src="docs/images/suggestions.png" width="49%">
  <img src="docs/images/menu-mode.png" width="49%">
</p>

**Fenêtre de confirmation avant de changer de mode, d'oublier l'historique ou de terminer la session**

<p>
  <img src="docs/images/fenetre-confirmation.png" width="49%">
  <img src="docs/images/fenetre-confirmation-sombre.png" width="49%">
</p>

#### Posts

**Lecture des posts : résultats en cartes**

<img src="docs/images/cartes.png" width="100%">

**Confirmation avant de publier un post, puis post publié**

<p>
  <img src="docs/images/post-confirmation-sombre.png" width="49%">
  <img src="docs/images/post-publie-sombre.png" width="49%">
</p>

**Post programmé à une date future, et photo publiée**

<p>
  <img src="docs/images/post-programme-sombre.png" width="49%">
  <img src="docs/images/photo-publiee-sombre.png" width="49%">
</p>

#### Couverture et photo de profil

**Confirmation avant de changer la couverture, puis couverture changée**

<p>
  <img src="docs/images/couverture-confirmation.png" width="49%">
  <img src="docs/images/couverture-resultat.png" width="49%">
</p>

**Photo de profil changée**

<img src="docs/images/photo-profil-resultat.png" width="100%">

#### Commentaires et Messenger

**Réponse publique à un commentaire, et réponse Messenger**

<p>
  <img src="docs/images/reponse-commentaire.png" width="49%">
  <img src="docs/images/messenger-reponse-sombre.png" width="49%">
</p>

**Conversations Messenger de la page, et résumé d'une conversation**

<p>
  <img src="docs/images/conversations-sombre.png" width="49%">
  <img src="docs/images/messenger-resume.png" width="49%">
</p>

#### Catalogue

**Confirmation d'un prix promotionnel, puis produit en promotion (ancien prix barré)**

<p>
  <img src="docs/images/produit-promotion-confirmation.png" width="49%">
  <img src="docs/images/produit-promotion-resultat.png" width="49%">
</p>

#### Lead Ads et publicités

**Formulaires Lead Ads de la page, et campagnes du compte sandbox (aucune dépense possible)**

<p>
  <img src="docs/images/lead-ads-formulaires.png" width="49%">
  <img src="docs/images/campagnes.png" width="49%">
</p>

#### Sécurité

**Mode dry-run : le bandeau reste visible pendant toute la conversation**

<img src="docs/images/dry-run-bandeau.png" width="100%">

**Suppression en dry-run : confirmation demandée, puis suppression seulement simulée**

<p>
  <img src="docs/images/suppression-dry-run.png" width="49%">
  <img src="docs/images/suppression-dry-run-resultat.png" width="49%">
</p>

**Confirmation refusée : rien n'est supprimé**

<img src="docs/images/refus.png" width="100%">

#### Suivi du travail de l'agent

**Étape en cours avec le bouton « Annuler la demande », et pause imposée par la limite de Groq**

<p>
  <img src="docs/images/progression-publication.png" width="49%">
  <img src="docs/images/progression-pause-groq.png" width="49%">
</p>

L'interface n'écoute que sur `127.0.0.1` et n'envoie aucune statistique d'usage. Polices et icônes sont
servies localement : aucune requête externe, à part les images de Facebook affichées dans les cartes.

## Installation

Python 3.12 (commandes pour Windows ; à adapter sous macOS ou Linux).

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

### Fichier `.env`

```
copy .env.example .env
```

Puis remplir `.env`, qui n'est jamais versionné :

| Variable | Rôle | Exemple |
|---|---|---|
| `FB_USER_TOKEN` | token utilisateur Facebook (Explorer de l'API Graph) | `EAA…` |
| `FB_APP_ID`, `FB_APP_SECRET` | application Meta, pour l'échange en token longue durée | |
| `FB_PAGE_ID` | page à gérer (vide : la première page du compte) | |
| `CATALOG_ID` | catalogue de produits | |
| `AD_ACCOUNT_ID` | compte publicitaire sandbox | `act_…` |
| `AD_ACCOUNT_MODE` | mode du compte publicitaire | `sandbox` |
| `ADS_ACCESS_TOKEN` | token de l'utilisateur système qui a la page et le compte sandbox | |
| `LLM_API_KEY` | clé Groq de l'agent (https://console.groq.com/keys) | `gsk_…` |

### Tokens

| Opérations | Token | Pourquoi |
|---|---|---|
| Page : posts, commentaires, photos, vidéos, Messenger, utilisateurs, Lead Ads | **token de page**, obtenu au démarrage à partir de `FB_USER_TOKEN` | ces actions sont faites au nom de la page |
| Catalogue : produits, collections, flux | **token utilisateur** (`FB_USER_TOKEN`) | le catalogue appartient à un Business Manager et se gère au nom d'une personne |
| Campagnes | `ADS_ACCESS_TOKEN` (utilisateur système), sinon `FB_USER_TOKEN` | le token doit voir à la fois la page et le compte publicitaire |

Le token de l'Explorer ne dure qu'une à deux heures. Pour un token d'environ 60 jours : le générer dans
l'[Explorer de l'API Graph](https://developers.facebook.com/tools/explorer/) avec les permissions
ci-dessous, l'ouvrir dans le [débogueur de tokens](https://developers.facebook.com/tools/debug/accesstoken/),
cliquer « Extend Access Token », puis copier le nouveau token dans `FB_USER_TOKEN`.

Permissions utiles, selon les opérations : `pages_show_list`, `pages_read_engagement`,
`pages_read_user_content`, `pages_manage_posts`, `pages_manage_engagement`, `pages_messaging`,
`pages_manage_metadata`, `catalog_management`, `business_management`, `leads_retrieval` (leads),
`ads_read` et `ads_management` (campagnes).

### Compte publicitaire sandbox

Meta refuse toute publicité sur un compte sans moyen de paiement, et le projet n'en ajoute jamais. Les
campagnes passent donc par un **compte sandbox**, qui ne diffuse rien et ne coûte rien :

1. Créer le compte sandbox de l'application (Meta for Developers, votre application, Marketing API,
   Outils) et le lier à la page.
2. Créer un **utilisateur système** de l'entreprise (Paramètres de l'entreprise) avec la page **et** le
   compte sandbox ; mettre son token dans `ADS_ACCESS_TOKEN`.
3. Faire accepter une fois la **politique de non-discrimination** par un administrateur de l'entreprise.
4. Dans `.env` : `AD_ACCOUNT_ID=act_…` et `AD_ACCOUNT_MODE=sandbox`.

## Lancement

**Agent en terminal** (commencer par le dry-run : lectures réelles, aucune écriture envoyée) :

```
.venv\Scripts\python.exe -m facebook_agent.agent --dry-run
.venv\Scripts\python.exe -m facebook_agent.agent
```

Commandes : `/aide`, `/reset` (vide l'historique), `/quitter`. Ctrl+C pendant une demande annule
seulement cette demande ; `o` / `n` répond à une confirmation.

**Menu interactif** (essayer chaque opération à la main ; il agit sur la vraie page) :

```
.venv\Scripts\python.exe -m facebook_agent
```

**Interface web**, depuis la racine du projet :

```
.venv\Scripts\python.exe -m streamlit run facebook_agent/web/app.py --server.address 127.0.0.1 --server.port 8501
```

Puis ouvrir http://127.0.0.1:8501. Pour arrêter : « Terminer la session » dans le menu ⋮, puis Ctrl+C dans
le terminal. Le même menu passe du mode dry-run au mode réel sans terminer la session.

Exemples de demandes à l'agent :

| Demande | Ce qui se passe |
|---|---|
| `Bonjour, que sais-tu faire ?` | présentation des domaines actifs, générée par le code (aucun appel au modèle) |
| `Liste mes 3 derniers posts` | lecture, puis cartes des posts |
| `Mets le T-shirt Nova en promotion à 12 DT` | recherche du produit, contrôle du prix, confirmation MODIFICATION, relecture du produit |
| `Réponds au commentaire « Il existe en taille M ? » : Oui, dans les trois couleurs !` | lecture des posts et de leurs commentaires, confirmation PUBLIC, réponse publiée au nom de la page |
| `Booster mon dernier post` | l'agent demande d'abord les pays visés, puis prépare campagne, ensemble et publicité sur le compte sandbox, chacun confirmé |

## Sécurité

- **Confirmation de toute écriture**, en 3 niveaux : IRRÉVERSIBLE (suppressions, Messenger, bannissement,
  import de flux), PUBLIC (publications, commentaires, couverture), MODIFICATION (catalogue, campagnes).
  L'objet visé est relu avant une suppression. Au plus 3 écritures par demande. Dry-run disponible.
- **Contexte injecté par le code** : les tokens et les ID de la page, du catalogue et du compte
  publicitaire n'apparaissent jamais dans les outils ; le modèle ne les voit pas.
- **Provenance des ID** : une écriture n'accepte que des ID tapés par l'utilisatrice ou lus dans un
  résultat ; la réponse ne cite que des ID de la demande en cours.
- **Injection** : les textes de tiers sont marqués comme non fiables ; une instruction cachée dans un
  commentaire ou un message est signalée et n'entraîne aucune action.
- **Réponses vérifiées** : une action annoncée mais refusée, une promotion annoncée sans prix envoyé ou un
  état contredit par la relecture sont remplacés par un message du code.
- **Argent** : compte relu avant chaque écriture (refusé s'il a un moyen de paiement ou a déjà dépensé),
  tout en PAUSED, budget minimal, aucune activation possible. Ces règles sont dans le code.
- **Données des leads** : affichées en entier à l'utilisatrice, masquées pour le modèle, absentes du
  journal.
- **Secrets** : `.env` jamais versionné ; tokens en mémoire seulement, jamais envoyés au modèle ni écrits
  dans le journal (`logs/`, ignoré par git), masqués dans les URL renvoyées par Facebook. Les exemples de
  réponses montrés dans les docstrings ne contiennent aucune vraie donnée.
- **Attention** : un `DELETE` sur l'ID d'un catalogue le supprime sans confirmation de Facebook ; l'agent
  vérifie qu'un ID est bien un flux du catalogue avant de le supprimer.

## Architecture

Les docstrings des opérations sont la source unique des outils de l'agent ; le code est organisé ainsi :

```
facebook_agent/
├── config.py, graph.py           configuration (.env) ; call_graph(), unique point d'appel de la Graph API
├── extract_function_doc_info.py  lecture structurée des docstrings
├── auth/, operations/            les 67 opérations
├── agent/                        outils générés, routage, boucle, exécuteur, limites Groq, journal
├── cli/                          menu interactif
└── web/                          interface web (contrôleur, cartes, page Streamlit)
docs/images/                      captures d'écran de la galerie
```

## Limites

- Le compte publicitaire est un compte sandbox : aucune dépense possible, les publicités restent en pause
  et ne sont jamais diffusées.
- Le quota gratuit de Groq (tokens par jour) peut mettre une demande en pause.

## Contexte

Projet réalisé lors d'un stage d'été (2025) chez Yperflow, encadré par M. Racel Maalej.

"""Web page of the agent (Streamlit). Launched by the user only, on 127.0.0.1 (see README, "Interface web").

The page only shows a WebSession (controller.py): the chat, the confirmation cards with buttons,
the progress of the request with "Annuler la demande", the DRY-RUN banner and the side panels. All
the logic, and every safety text, is that of the terminal agent. Theme and fonts: .streamlit/config.toml
and static/fonts (served by the app, no external request). Icons: Material only, no emoji.
"""
import hashlib
import math
import threading
from html import escape

import streamlit as st

from facebook_agent import config
from facebook_agent.web import controller as web
from facebook_agent.web import prefs
from facebook_agent.web.cards import THUMB_ICONS

REFRESH = 0.5  # secondes entre deux lectures de la demande en cours
CONFIRM_MINUTES = int(web.CONFIRM_TIMEOUT // 60)
APP_TITLE = "Agent de gestion Facebook"
LEADS_TITLE = "Réponses complètes des leads"
LEADS_NOTE = "Visible par toi seule, jamais envoyé au modèle ni au journal."
DRY_RUN_BANNER = "DRY-RUN : aucune écriture n'est envoyée"
START_SUB = "Active le dry-run pour tester sans rien modifier, puis lance l'agent."
PAGE_UNKNOWN = "Page configurée"
INTRO = ("Page, Messenger, catalogue, Lead Ads et publicités : écris une demande, l'agent choisit les actions, te "
         "montre chaque modification et attend ta confirmation.")
SCOPE = "Tout porte sur ta page et ses comptes professionnels, jamais sur ton profil personnel."
# Fonctionnalités du panneau de gauche : (titre, icône Material, description) ; la dernière dépend du compte pub
FEATURES = (("Page Facebook", ":material/article:",
             "Posts, commentaires et modération, photos et couverture, vidéos de la page."),
            ("Messenger de la page", ":material/forum:",
             "Conversations des clients avec la page : lire, répondre, réponses rapides."),
            ("Catalogue de produits", ":material/shopping_bag:",
             "Catalogue relié à la page : produits, prix et promotions, collections, flux."),
            ("Lead Ads de la page", ":material/assignment:",
             "Formulaires de contact et prospects, données personnelles masquées."),
            ("Publicités", ":material/campaign:",
             "Compte publicitaire : campagnes, ensembles et publicités en pause, booster un post de la page."))
START_NOTE = "Chaque publication, modification ou suppression attend ta confirmation."
DRY_RUN_NOTE = "Lectures réelles, aucune écriture envoyée"
OUTDATED = ("L'interface a été mise à jour pendant la session : celle-ci est terminée (tokens oubliés). "
            "Démarre une nouvelle session.")
LEVELS = {"IRRÉVERSIBLE": ("red", ":material/warning:", "irreversible"),
          "PUBLIC": ("orange", ":material/public:", "public"),
          "MODIFICATION": ("blue", ":material/edit:", "modification")}
STATE_BADGES = {"créé": "green", "publié": "green", "publiée": "green", "envoyé": "green", "envoyée": "green",
                "changée": "blue", "modifié": "blue", "supprimé": "red", "supprimée": "red", "archivé": "gray", "simulé": "orange"}
TOAST_SECONDS = 4  # les notifications (« Aide affichée. ») disparaissent seules
CSS = """<style>
@font-face { font-family: "Inter"; src: url("app/static/fonts/InterVariable.woff2") format("woff2");
  font-weight: 100 900; font-style: normal; font-display: swap; }
@font-face { font-family: "JetBrains Mono"; src: url("app/static/fonts/JetBrainsMono-Regular.woff2") format("woff2");
  font-weight: 400; font-style: normal; font-display: swap; }
@font-face { font-family: "JetBrains Mono"; src: url("app/static/fonts/JetBrainsMono-Bold.woff2") format("woff2");
  font-weight: 700; font-style: normal; font-display: swap; }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp table,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, [data-testid="stSidebar"],
[data-testid="stToast"] { font-family: "Inter", "Segoe UI", system-ui, sans-serif; }
.stApp code, .stApp pre { font-family: "JetBrains Mono", monospace; }

/* Couleurs : variables qui suivent le thème réellement affiché (Streamlit pose color-scheme sur l'application).
   Aussi sur :root : le menu ⋮ (popover) s'ouvre dans une couche hors de .stApp. */
:root, .stApp, [data-testid="stSidebar"], [data-testid="stPopoverBody"] {
  --fa-page: light-dark(#F4F5F8, #0F1117);
  --fa-sidebar: light-dark(#EEF0F4, #12151D);
  --fa-card: light-dark(#FFFFFF, #171A23);
  --fa-line: light-dark(#E5E7EB, #2A2F3A);
  --fa-control: light-dark(#D1D5DB, #3A4150);
  --fa-text: light-dark(#1F2937, #E5E7EB);
  --fa-muted: light-dark(#6B7280, #9CA3AF);
  --fa-accent: light-dark(#4F46E5, #6366F1);
  --fa-accent-soft: light-dark(#EEF2FF, #1E1B4B);
  --fa-shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10);
  --fa-shadow-input: 0 2px 6px rgba(16,24,40,.08);
}
.stApp, [data-testid="stAppViewContainer"] { background: var(--fa-page); }

/* Barre latérale */
[data-testid="stSidebar"], [data-testid="stSidebarContent"] { background: var(--fa-sidebar) !important; }
[data-testid="stSidebar"] { border-right: 1px solid var(--fa-line); }
/* Boutons de repli et d'ouverture de la barre latérale : icône visible, couleurs du thème (jamais un carré vide) */
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] {
  background: var(--fa-card) !important; border: 1px solid var(--fa-line) !important; color: var(--fa-text) !important; }
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"], [data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg { color: var(--fa-text) !important; fill: currentColor; opacity: 1 !important; }
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] { gap: 14px; }

/* Cartes : barre latérale, confirmations, aide, écran de démarrage */
[class*="st-key-side-"], [class*="st-key-card-"], .st-key-start-frame {
  background: var(--fa-card) !important; color: var(--fa-text); border: 1px solid var(--fa-line) !important;
  border-radius: 12px !important; box-shadow: var(--fa-shadow); height: auto !important; min-height: 0; }
[class*="st-key-side-"] { padding: 14px 16px !important; gap: 10px !important; }
[class*="st-key-card-"] { padding: 16px 18px !important; }
[class*="st-key-card-irreversible"] { border-left: 4px solid #DC2626 !important; }
[class*="st-key-card-public"] { border-left: 4px solid #EA580C !important; }
[class*="st-key-card-modification"] { border-left: 4px solid #2563EB !important; }
.fa-section-title { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em;
  line-height: 1.4; color: var(--fa-muted); margin: 0 0 10px; padding: 0; }
[class*="st-key-side-"] p { font-size: 14px; line-height: 1.5; }

/* Boutons secondaires (suggestions, Aide, Vider l'historique, Terminer la session…) */
.stApp [data-testid="stBaseButton-secondary"] { background: var(--fa-card); color: var(--fa-text);
  border: 1px solid var(--fa-control); box-shadow: var(--fa-shadow); }
.stApp [data-testid="stBaseButton-secondary"]:hover { border-color: var(--fa-accent); background: var(--fa-accent-soft);
  color: var(--fa-text); }

/* En-tête compact : titre, utilisateur, petits boutons à icône */
[data-testid="stMainBlockContainer"] { padding-top: 1.25rem !important; }
/* En-tête fixé en haut pendant le défilement. Ce qui défile est la zone principale (stMain), et Streamlit
   enveloppe chaque conteneur dans un stLayoutWrapper : c'est ce parent, repéré par le marqueur (la clé
   app-head), qui doit coller (un enfant collant ne bouge pas dans un parent de sa propre hauteur). Fond
   opaque du thème, légère ombre en bas ; aucun parent ne coupe le débordement. Le conteneur collé
   (app-top) porte l'en-tête et, en dry-run, le bandeau DRY-RUN juste dessous : les deux restent visibles. */
[data-testid="stLayoutWrapper"]:has(> .st-key-app-top),
.st-key-app-top { position: sticky !important; top: 0; z-index: 999; background: var(--fa-page);
  box-shadow: 0 6px 8px -6px rgba(16,24,40,.25); }
.st-key-app-top { padding-bottom: 8px; gap: 0 !important; }
.st-key-app-head { padding: 8px 0; }
[data-testid="stMainBlockContainer"], [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
  overflow: visible !important; }
.fa-head-title { font-size: 20px; font-weight: 700; line-height: 1.3; color: var(--fa-text); margin: 0; }
.fa-head-user { font-size: 13px; line-height: 1.4; color: var(--fa-muted); margin: 2px 0 0; }
[class*="st-key-head-"] button { min-height: 34px; padding: 4px 10px; }
.fa-dryrun { background: light-dark(#FFF7ED, #2A1A0B); color: light-dark(#9A3412, #FDBA74);
  border: 1px solid #EA580C; border-left: 4px solid #EA580C; border-radius: 10px; padding: 10px 14px;
  font-size: 14px; font-weight: 600; line-height: 1.4; margin: 0; }

/* Suggestions : onglets soulignés par domaine, puis grille de cartes cliquables */
[class*="st-key-suggest-"] [data-testid="stTabs"] [role="tab"] p { font-size: 14px; font-weight: 600; }
/* Carte = vrai bouton compact : icône et titre complet (retour à la ligne, jamais coupé), description en
   infobulle, même hauteur pour toutes ; texte en couleur normale : elles n'ont pas l'air désactivées */
[class*="st-key-sugcard-"] button { justify-content: flex-start; text-align: left; height: 64px; min-height: 64px;
  padding: 6px 12px; background: var(--fa-card); color: var(--fa-text); border: 1px solid var(--fa-line);
  border-radius: 12px; box-shadow: var(--fa-shadow); cursor: pointer; transition: border-color .15s, background .15s; }
[class*="st-key-sugcard-"] button:hover { border-color: var(--fa-accent); background: var(--fa-accent-soft); }
[class*="st-key-sugcard-"] button [data-testid="stIconMaterial"] { font-size: 19px; color: var(--fa-accent); }
[class*="st-key-sugcard-"] button div, [class*="st-key-sugcard-"] button p { white-space: normal; overflow: visible;
  text-overflow: clip; }
[class*="st-key-sugcard-"] button p { font-size: 13.5px; font-weight: 600; line-height: 1.3; margin: 0;
  overflow-wrap: break-word; color: var(--fa-text) !important; }
/* Fenêtre « Suggestions » : assez large pour 3 cartes par ligne */
[data-testid="stPopoverBody"]:has([class*="st-key-suggest-"]) { width: min(820px, 94vw); max-width: 94vw; }
[class*="st-key-suggest-"] [data-testid="stTabPanel"] { padding-bottom: 0; }
[class*="st-key-suggest-"] [data-testid="stVerticalBlock"] { gap: 8px; }

/* Menu ⋮ de l'application (popover) */
.st-key-head-menu [data-testid="stPopover"] button { border: 1px solid var(--fa-control); background: var(--fa-card);
  box-shadow: var(--fa-shadow); }
/* Menus ouverts (⋮, Suggestions) : fond opaque et ombre nette, bien détachés des cartes en dessous */
[data-testid="stPopoverBody"] { background: var(--fa-card) !important; color: var(--fa-text);
  border: 1px solid var(--fa-line) !important; border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0,0,0,.28), 0 2px 8px rgba(0,0,0,.18) !important; }
[data-testid="stPopoverBody"] [data-testid="stBaseButton-secondary"] { background: var(--fa-card);
  color: var(--fa-text); border: 1px solid var(--fa-line); }
[data-testid="stPopoverBody"] [data-testid="stBaseButton-secondary"]:hover { border-color: var(--fa-accent);
  background: var(--fa-accent-soft); color: var(--fa-text); }
[data-testid="stPopoverBody"] [data-testid="stBaseButton-secondary"] p,
[data-testid="stPopoverBody"] label, [data-testid="stPopoverBody"] label p,
[data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p { color: var(--fa-text) !important; }
/* Fenêtres de confirmation (Oublier l'historique, Terminer la session) : fond opaque, texte et boutons lisibles
   en clair comme en sombre */
[data-testid="stDialog"] [role="dialog"] { background: var(--fa-card) !important; color: var(--fa-text) !important;
  border: 1px solid var(--fa-line) !important; border-radius: 14px !important; }
[data-testid="stDialog"] [role="dialog"] p, [data-testid="stDialog"] [role="dialog"] h2 {
  color: var(--fa-text) !important; }
[data-testid="stDialog"] [data-testid="stBaseButton-secondary"] { background: var(--fa-card) !important;
  color: var(--fa-text) !important; border: 1px solid var(--fa-control) !important; }
[data-testid="stDialog"] [data-testid="stBaseButton-secondary"] p { color: var(--fa-text) !important; }
[data-testid="stDialog"] [data-testid="stBaseButton-secondary"]:hover { border-color: var(--fa-accent) !important;
  background: var(--fa-accent-soft) !important; }
/* Croix de fermeture d'une fenêtre (un svg dessiné en currentColor) : couleur du texte de la fenêtre */
[data-testid="stDialog"] button[aria-label="Close"] { color: var(--fa-text) !important; }

/* Cartes de résultats (posts…) : construites par le code, jamais envoyées au modèle */
[class*="st-key-rcard-"] { background: var(--fa-card); color: var(--fa-text); border: 1px solid var(--fa-line);
  border-radius: 12px; box-shadow: var(--fa-shadow); padding: 12px 14px; gap: 8px; }
.fa-rcard { display: flex; gap: 14px; align-items: flex-start; }
.fa-rbody { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.fa-rtext { font-size: 14.5px; line-height: 1.45; color: var(--fa-text); margin: 0; }
.fa-rsub { font-size: 13px; line-height: 1.4; color: var(--fa-muted); margin: 0; }
.fa-rlink { font-size: 13px; font-weight: 600; color: var(--fa-accent); text-decoration: none; display: inline-flex;
  align-items: center; gap: 4px; }
.fa-rlink .fa-icon { font-size: 16px; }
.fa-thumb { position: relative; flex: none; width: 96px; height: 96px; border-radius: 10px; overflow: hidden;
  background: var(--fa-line); display: grid; place-items: center; }
.fa-gcard { display: flex; flex-direction: column; gap: 4px; }
.fa-th { margin: 0; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  color: var(--fa-muted); }
.fa-td { margin: 0; font-size: 14px; line-height: 1.4; color: var(--fa-text); }
.fa-thread { display: flex; flex-direction: column; gap: 8px; }
.fa-bubble { max-width: 78%; padding: 8px 12px; border-radius: 14px; }
.fa-theirs { align-self: flex-start; background: var(--fa-page); border: 1px solid var(--fa-line); }
.fa-mine { align-self: flex-end; background: var(--fa-accent-soft); border: 1px solid var(--fa-accent); }
.fa-price { margin: 0; font-size: 14px; color: var(--fa-text); }
.fa-price s { color: var(--fa-muted); font-size: 12.5px; margin-left: 4px; }
.fa-badges { margin: 0; display: flex; flex-wrap: wrap; gap: 4px; }
.fa-badge-s { font-size: 12px; font-weight: 600; line-height: 1.5; padding: 1px 8px; border-radius: 999px; }
.fa-green { background: light-dark(#DCFCE7, #14532D); color: light-dark(#166534, #BBF7D0); }
.fa-red { background: light-dark(#FEE2E2, #7F1D1D); color: light-dark(#991B1B, #FECACA); }
.fa-orange { background: light-dark(#FFEDD5, #7C2D12); color: light-dark(#9A3412, #FED7AA); }
.fa-blue { background: light-dark(#DBEAFE, #1E3A8A); color: light-dark(#1E40AF, #BFDBFE); }
.fa-gray { background: light-dark(#F3F4F6, #2A2F3A); color: light-dark(#374151, #D1D5DB); }
.fa-gcard .fa-thumb { width: 100%; height: auto; aspect-ratio: 4 / 3; }
.fa-gcard .fa-rtext { font-size: 13.5px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.fa-thumb > .fa-icon { font-size: 28px; color: var(--fa-muted); }
.fa-thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
/* Petit bouton « ID » des cartes : l'ID s'ouvre dans un bloc de code avec l'icône de copie de Streamlit ;
   fond de carte, bordure et texte du thème (jamais une pastille blanche en sombre) */
[class*="st-key-rcard-"] [data-testid="stPopover"] button { min-height: 28px; padding: 2px 10px; font-size: 12.5px;
  background: var(--fa-card) !important; border: 1px solid var(--fa-line) !important; color: var(--fa-text) !important; }
[class*="st-key-rcard-"] [data-testid="stPopover"] button p,
[class*="st-key-rcard-"] [data-testid="stPopover"] button span { color: var(--fa-text) !important; }

/* Blocs de code (ID, détails, texte complet) : lisibles dans les deux thèmes, aussi dans un menu ouvert */
.stApp [data-testid="stCode"] pre, [data-testid="stPopoverBody"] [data-testid="stCode"] pre {
  background: light-dark(#F4F5F8, #12151D) !important; color: var(--fa-text) !important; }
/* Bouton de copie des blocs de code : fond de carte et icône du thème (jamais un carré blanc en sombre) */
[data-testid="stCode"] button { background: var(--fa-card) !important; color: var(--fa-text) !important;
  border: 1px solid var(--fa-line) !important; }
[data-testid="stCode"] button svg, [data-testid="stCode"] button [data-testid="stIconMaterial"] {
  color: var(--fa-text) !important; fill: currentColor; }

/* Formulaire de démarrage : lignes à icône, cartes de même espacement (gap de .st-key-start-form) */
.fa-field { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 15px; line-height: 1.4;
  color: var(--fa-text); }
.fa-field .fa-icon { font-size: 20px; color: var(--fa-accent); }
.fa-field.fa-quiet, .fa-field.fa-quiet .fa-icon { color: var(--fa-muted); font-size: 13.5px; }
.fa-dry { display: flex; align-items: center; gap: 12px; margin: 0; }
.fa-dry .fa-icon { font-size: 22px; color: var(--fa-accent); }
.fa-dry b { display: block; font-size: 15px; line-height: 1.35; color: var(--fa-text); }
.fa-dry span.fa-dry-desc { display: block; font-size: 13px; line-height: 1.4; color: var(--fa-muted); }

/* Activité de la session : mini-cartes (icône du type, nom, heure, badge d'état) */
.fa-empty { margin: 4px 0; display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center;
  color: var(--fa-muted); font-size: 13.5px; }
.fa-empty .fa-icon { font-size: 26px; color: var(--fa-muted); }
[class*="st-key-obj-"] { background: var(--fa-card); border: 1px solid var(--fa-line); border-radius: 10px;
  box-shadow: var(--fa-shadow); padding: 8px 10px; gap: 6px; }
.fa-mini { display: flex; align-items: center; gap: 8px; margin: 0; min-width: 0; }
.fa-mini > .fa-icon { font-size: 18px; color: var(--fa-accent); flex: none; }
.fa-mini-body { min-width: 0; flex: 1; }
.fa-mini-title { margin: 0; font-size: 13.5px; font-weight: 600; line-height: 1.35; color: var(--fa-text);
  white-space: normal; overflow-wrap: anywhere; }
/* Pagination de l'activité : « ‹ Plus récentes », « page 1 / 3 », « Plus anciennes › » */
.st-key-activity-pages { justify-content: space-between; }
.st-key-activity-pages button { min-height: 28px; padding: 0 4px; }
.st-key-activity-pages button p { font-size: 12.5px; color: var(--fa-accent); }
.fa-pages { margin: 0; font-size: 12px; color: var(--fa-muted); white-space: nowrap; }
.fa-mini-sub { margin: 0; font-size: 12px; line-height: 1.3; color: var(--fa-muted); }
[class*="st-key-obj-"] [data-testid="stPopover"] button { min-height: 26px; padding: 1px 8px; font-size: 12px;
  background: var(--fa-card) !important; border: 1px solid var(--fa-line) !important; color: var(--fa-text) !important; }

/* Zone de saisie du chat */
[data-testid="stChatInput"] { background: var(--fa-card); border: 1px solid var(--fa-control) !important;
  border-radius: 12px; box-shadow: var(--fa-shadow-input); }
[data-testid="stChatInput"]:focus-within { border-color: var(--fa-accent) !important; }
/* Un seul bloc : les cadres internes de Streamlit sont transparents (jamais un champ sombre dans un cadre clair) */
[data-testid="stChatInput"] div, [data-testid="stChatInputTextArea"] { background-color: transparent !important;
  border-color: transparent !important; }
[data-testid="stChatInputTextArea"] { color: var(--fa-text) !important; }
[data-testid="stChatInputTextArea"]::placeholder, [data-testid="stChatInput"] textarea::placeholder {
  color: var(--fa-muted) !important; -webkit-text-fill-color: var(--fa-muted) !important; opacity: 1 !important; }
/* Bouton « Suggestions » au-dessus de la zone de saisie : mêmes couleurs que les cartes */
.st-key-suggest-button [data-testid="stPopover"] button { background: var(--fa-card) !important;
  border: 1px solid var(--fa-line) !important; color: var(--fa-text) !important; box-shadow: var(--fa-shadow); }
.st-key-suggest-button [data-testid="stPopover"] button p { color: var(--fa-text) !important; }
[data-testid="stChatInputSubmitButton"] { background: transparent !important; color: var(--fa-accent) !important; }

/* Barres du quota Groq : fond de la piste */
[data-testid="stProgressBarTrack"] { background-color: var(--fa-line) !important; }

/* Infobulles (react-aria dans Streamlit 1.66) : elles restent ouvertes tant que la souris est « dans »
   l'infobulle, et ne partent qu'à la fin de leur animation de sortie. Jamais survolables, retirées sans
   attendre : chacune disparaît dès que la souris quitte l'élément. */
[data-testid="stTooltipContent"], .react-aria-Tooltip, [role="tooltip"] { pointer-events: none !important; }
.react-aria-Tooltip[data-exiting], [role="tooltip"][data-exiting] { animation: none !important;
  transition: none !important; }

/* Aide : une carte par domaine actif, puis des règles courtes à icônes */
.fa-help-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr)); gap: 10px; }
.fa-help-card { display: flex; gap: 10px; align-items: flex-start; min-width: 0; background: var(--fa-page);
  border: 1px solid var(--fa-line); border-radius: 10px; padding: 10px 12px; }
.fa-help-card > .fa-icon { width: 32px; height: 32px; border-radius: 8px; background: var(--fa-accent-soft);
  color: var(--fa-accent); display: grid; place-items: center; flex: none; font-size: 19px; }
.fa-help-card b { display: block; font-size: 14.5px; line-height: 1.35; color: var(--fa-text); }
.fa-help-card span:not(.fa-icon) { display: block; font-size: 13px; line-height: 1.45; color: var(--fa-muted); }
.fa-help-rules { list-style: none; padding: 0 !important; margin: 14px 0 0 !important; display: grid; gap: 8px; }
.fa-help-rules li { display: flex; gap: 10px; align-items: flex-start; margin: 0 !important; font-size: 14px;
  line-height: 1.45; color: var(--fa-text); }
.fa-help-rules .fa-icon { font-size: 18px; color: var(--fa-accent); flex: none; }

/* Largeur : aucun débordement horizontal (colonnes rétrécissables, textes longs et ID renvoyés à la ligne) */
[data-testid="stMain"] { overflow-x: hidden; }
[data-testid="stColumn"], [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"] > div { min-width: 0; }
.stApp p, .stApp li, .stApp td, .stApp th, .stApp code, .fa-help, .fa-rtext, .fa-td { overflow-wrap: anywhere; }
.stApp [data-testid="stCode"] pre, .stApp [data-testid="stCode"] code { white-space: pre-wrap !important; }
.fa-head { min-width: 0; flex: 1; }
/* Petit écran : la barre de Streamlit (bouton de la barre latérale) occupe le haut ; l'en-tête colle juste dessous,
   à sa place normale (aucun saut, aucun chevauchement des suggestions) */
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 3.75rem !important; padding-left: 1rem !important;
    padding-right: 1rem !important; }
  [data-testid="stLayoutWrapper"]:has(> .st-key-app-top), .st-key-app-top { top: 3.75rem; }
  [data-testid="stHeader"] { background: var(--fa-page); }
}

/* Écran de démarrage (d'après la maquette de l'interface), centré verticalement dans la fenêtre */
[data-testid="stMainBlockContainer"]:has(.st-key-start-frame) { min-height: 100dvh; display: flex;
  flex-direction: column; justify-content: center; padding-top: 2rem !important; padding-bottom: 2rem; }
.st-key-start-frame { max-width: 1180px; width: 100%; margin: 0 auto; overflow: hidden; padding: 0 !important; }
.st-key-start-theme { min-height: 0; }
.st-key-start-brand { background: linear-gradient(150deg, #4F46E5 0%, #4338CA 55%, #312E81 100%);
  padding: 40px 36px; min-height: 560px; height: 100%; }
.fa-brand, .fa-brand * { color: #FFFFFF; }
.fa-brand .brand-title { font-size: 30px; line-height: 1.2; font-weight: 700; margin: 0 0 8px; padding: 0;
  letter-spacing: -0.01em; }
.fa-brand .brand-intro { margin: 0; font-size: 15px; line-height: 1.5; opacity: .85; max-width: 440px; }
.fa-brand .brand-scope { margin: 10px 0 0; font-size: 13px; line-height: 1.5; opacity: .75; }
/* Cartes alignées sur le bord gauche du titre (Streamlit ajoute un retrait aux listes) */
.fa-feats { list-style: none; padding: 0 !important; padding-inline-start: 0 !important; margin: 28px 0 0 !important;
  display: grid; gap: 12px; }
.fa-feats li { display: flex; gap: 14px; align-items: flex-start; margin: 0 !important;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.12); border-radius: 12px; padding: 12px 14px; }
.fa-feats li.fa-off { opacity: .55; }
.fa-badge { width: 36px; height: 36px; border-radius: 9px; background: rgba(255,255,255,.16); flex: none;
  display: grid; place-items: center; }
.fa-icon { font-family: "Material Symbols Rounded"; font-size: 20px; line-height: 1; font-weight: normal;
  font-style: normal; letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr;
  font-feature-settings: "liga"; -webkit-font-feature-settings: "liga"; -webkit-font-smoothing: antialiased; }
.fa-feats b { display: block; font-weight: 600; font-size: 15px; line-height: 1.35; }
.fa-feats .fa-desc { display: block; opacity: .82; font-size: 13.5px; line-height: 1.45; margin: 2px 0 0; }
.st-key-start-form { padding: 40px 36px; min-height: 560px; justify-content: center; background: var(--fa-card);
  color: var(--fa-text); gap: 16px !important; }
.st-key-start-form h3 { font-size: 22px; line-height: 1.3; padding: 0 0 4px; }
.st-key-start-sub p { color: var(--fa-muted); font-size: 14px; line-height: 1.5; }
.st-key-field-page, .st-key-field-dry { border: 1px solid var(--fa-line); border-radius: 10px; padding: 12px 14px;
  height: auto; gap: 8px; background: var(--fa-card); box-shadow: var(--fa-shadow); }
.st-key-start-form button[kind="primary"] { border-radius: 10px; padding: 13px 16px; font-weight: 600; }
/* Interrupteur « Mode sombre » de l'écran de démarrage : aucun fond derrière lui ni derrière son libellé
   (le rail de l'interrupteur garde ses couleurs) */
[data-testid="stLayoutWrapper"]:has(> .st-key-start-theme), .st-key-start-theme,
.st-key-start-theme [data-testid="stElementContainer"], .st-key-start-theme [data-testid="stCheckbox"],
.st-key-start-theme [data-testid="stCheckbox"] > label, .st-key-start-theme [data-testid="stWidgetLabel"],
.st-key-start-theme [data-testid="stWidgetLabel"] * { background: transparent !important; box-shadow: none !important;
  border: 0 !important; }
/* Boutons pleins (indigo : Démarrer la session, Confirmer, Oublier, Terminer, Passer en mode réel…) : texte et
   icône blancs, en clair comme en sombre, dans la page comme dans une fenêtre */
.stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primary"] *,
[data-testid="stDialog"] [role="dialog"] [data-testid="stBaseButton-primary"],
[data-testid="stDialog"] [role="dialog"] [data-testid="stBaseButton-primary"] * { color: #FFFFFF !important; }
.st-key-start-note p { color: var(--fa-muted); font-size: 13px; line-height: 1.5; text-align: center; }

/* Menu ⋮ de Streamlit masqué : remplacé par le menu de l'application dans l'en-tête */
[data-testid="stMainMenu"], [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"] {
  display: none !important; }
[data-testid="stHeader"] { background: transparent; }
</style>"""


def material_name(icon: str) -> str:
    """Name of a Material icon for local HTML (":material/article:" -> "article").

    Args:
        icon: Streamlit icon string.

    Returns:
        The ligature name, drawn with the Material Symbols font already loaded by Streamlit.
    """
    return icon.removeprefix(":material/").removesuffix(":")


@st.cache_data(show_spinner=False)
def brand_html(ads_configured: bool) -> str:
    """Left panel of the start screen in local HTML (title, introduction, scope, five features).

    Local HTML keeps the spacing of the mockup: no negative margin of Streamlit's markdown, so no text
    touches the bottom of a card. Every text is a constant of this file.

    Args:
        ads_configured: False greys the "Publicités" card and adds "non configuré".

    Returns:
        The HTML for st.html.
    """
    items = []
    for title, icon, description in FEATURES:
        off = title == "Publicités" and not ads_configured
        items.append(f'<li class="{"fa-off" if off else "fa-on"}"><div class="fa-badge"><span class="fa-icon">'
                     f'{material_name(icon)}</span></div><div><b>{title}{" · non configuré" if off else ""}</b>'
                     f'<span class="fa-desc">{description}</span></div></li>')
    return (f'<div class="fa-brand"><h2 class="brand-title">{APP_TITLE}</h2><p class="brand-intro">{INTRO}</p>'
            f'<p class="brand-scope">{SCOPE}</p><ul class="fa-feats">{"".join(items)}</ul></div>')


def section_title(title: str) -> None:
    """Title of a sidebar card: 12px, upper case, grey, line-height 1.4, 10px below (local HTML, no overlap).

    Args:
        title: The title (written in normal case, shown in upper case by the CSS).
    """
    st.html(f'<p class="fa-section-title">{title}</p>')


DARK_KEY = "dark_mode"  # choix du mode sombre, gardé pendant la session (même hors de l'écran du chat)
DARK_CSS = """<style>
/* Mode sombre (menu ⋮) : nos variables passent en sombre (color-scheme) et les composants natifs suivent */
:root, .stApp, [data-testid="stSidebar"], [data-testid="stBottom"], [data-baseweb="popover"],
[data-testid="stPopoverBody"], [data-testid="stToastContainer"], [data-testid="stDialog"] { color-scheme: dark !important; }
/* Bouton principal d'une fenêtre (Oublier, Terminer) : texte blanc sur indigo */
[data-testid="stDialog"] [data-testid="stBaseButton-primary"] p { color: #FFFFFF !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] { background: var(--fa-page) !important; }
.stApp p, .stApp li, .stApp label, .stApp span:not(.fa-icon):not([data-testid="stIconMaterial"]), .stApp h1,
.stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp summary, .stApp td, .stApp th,
[data-testid="stPopoverBody"] p, [data-testid="stToast"] p { color: var(--fa-text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--fa-muted) !important; }
.fa-brand, .fa-brand * { color: #FFFFFF !important; }
[data-testid="stExpander"] details { background: var(--fa-card) !important; border-color: var(--fa-line) !important; }
/* En-tête d'un bloc replié (Détails…), ouvert ou fermé : fond sombre et texte clair */
[data-testid="stExpander"] summary, [data-testid="stExpander"] details[open] > summary {
  background: var(--fa-card) !important; color: var(--fa-text) !important; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span:not([data-testid="stIconMaterial"]) {
  color: var(--fa-text) !important; }
[data-testid="stExpander"] summary:hover p { color: var(--fa-accent) !important; }
/* Bulle des messages de l'utilisatrice : indigo foncé, texte clair */
[data-testid="stChatMessage"]:has([class*="st-key-umsg-"]) { background: var(--fa-accent-soft) !important; }
[data-testid="stChatMessage"]:has([class*="st-key-umsg-"]) * { color: var(--fa-text) !important; }
[data-testid="stTabs"] [role="tablist"] { border-color: var(--fa-line) !important; }
[data-testid="stTabs"] [role="tab"] p { color: var(--fa-muted) !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] p { color: var(--fa-accent) !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: var(--fa-text) !important; }
[data-testid="stChatInput"] textarea::placeholder { color: var(--fa-muted) !important;
  -webkit-text-fill-color: var(--fa-muted) !important; }
[data-testid="stPopoverBody"], [data-testid="stToast"] { background: var(--fa-card) !important;
  border: 1px solid var(--fa-line) !important; color: var(--fa-text) !important; }
.stApp [data-baseweb="select"] > div, .stApp input, .stApp textarea { background: var(--fa-card) !important;
  color: var(--fa-text) !important; border-color: var(--fa-control) !important; }
[data-testid="stTable"] table, [data-testid="stTable"] th, [data-testid="stTable"] td {
  background: var(--fa-card) !important; color: var(--fa-text) !important; border-color: var(--fa-line) !important; }
.stApp [data-testid="stBaseButton-primary"] p { color: #FFFFFF !important; }
/* Interrupteurs (dry-run, mode sombre) : rail visible, couleur de bordure éteint, indigo allumé */
[data-testid="stCheckbox"] label > div:has(> div):not([data-testid="stWidgetLabel"]):not(:has([data-testid="stWidgetLabel"])) {
  background-color: var(--fa-line) !important; }
[data-testid="stCheckbox"] label[data-selected] > div:has(> div):not([data-testid="stWidgetLabel"]):not(:has([data-testid="stWidgetLabel"])) {
  background-color: var(--fa-accent) !important; }
</style>"""


def dark_mode() -> bool:
    """Whether the dark mode is on (switch of the ⋮ menu; the last choice, kept in web_prefs.json).

    Returns:
        The choice kept in the session, read from the local file the first time.
    """
    if DARK_KEY not in st.session_state:
        st.session_state[DARK_KEY] = prefs.load()["dark"]
    return bool(st.session_state[DARK_KEY])


def remember_dark_mode(key: str = "menu-dark") -> None:
    """Keep the choice of a switch for the whole session (the switch itself is not always drawn) and for the
    next start (web_prefs.json).

    Args:
        key: Key of the switch: "menu-dark" (⋮ menu) or "start-dark" (start screen).
    """
    st.session_state[DARK_KEY] = bool(st.session_state.get(key))
    prefs.save(dark=st.session_state[DARK_KEY])


DRY_KEY = "dry_run_choice"  # interrupteur « Mode dry-run » de l'écran de démarrage


def remember_dry_run() -> None:
    """Keep the dry-run switch of the start screen for the next start (web_prefs.json)."""
    prefs.save(dry_run=bool(st.session_state.get(DRY_KEY)))


def switch_mode(session: web.WebSession) -> None:
    """Switch "Mode dry-run" of the ⋮ menu: open the window that confirms the new mode; nothing changes before
    its button (the switch keeps showing the mode of the session).

    Args:
        session: Web session shown by the page.
    """
    wanted = bool(st.session_state.get("menu-dry"))
    if wanted != session.dry_run and not session.busy and session.pending is None:
        st.session_state[DIALOG_KEY] = "dry" if wanted else "real"


def dark_switch(key: str) -> None:
    """The "Mode sombre" switch: the same setting in the ⋮ menu and on the start screen.

    Args:
        key: Key of the widget ("menu-dark" or "start-dark").
    """
    st.toggle("Mode sombre", key=key, value=dark_mode(), on_change=remember_dark_mode, args=(key,))


@st.cache_data(show_spinner=False)
def page_css(dark: bool = False) -> str:
    """CSS of the page; its colours follow the theme shown (light-dark), no external request.

    Args:
        dark: True adds DARK_CSS (dark mode chosen in the ⋮ menu).

    Returns:
        A <style> block (two in dark mode) for st.html.
    """
    return CSS + DARK_CSS if dark else CSS


@st.cache_resource(show_spinner=False)
def start_registry(account_id: str | None, mode: str | None):
    """Tools of the start screen, built once (about 75 ms) for a given ad account configuration.

    Args:
        account_id: AD_ACCOUNT_ID (cache key only).
        mode: AD_ACCOUNT_MODE (cache key only).

    Returns:
        The ToolRegistry of session_registry().
    """
    return web.session_registry()


@st.cache_resource(show_spinner=False)
def prewarm() -> threading.Thread:
    """Import the LLM client and pandas in the background once the first screen is drawn (no network).

    "Démarrer la session" then no longer waits for the openai import (about 4 s), nor the first table
    of a confirmation for pandas.

    Returns:
        The background thread.
    """
    def run() -> None:
        """Import the heavy modules."""
        import openai  # noqa: F401
        import pandas  # noqa: F401
    thread = threading.Thread(target=run, daemon=True, name="prewarm-imports")
    thread.start()
    return thread


def short_number(value: int) -> str:
    """Number with a thin space between thousands ("182 400").

    Args:
        value: The number.

    Returns:
        The formatted number.
    """
    return f"{value:,}".replace(",", " ")


# --- Écran de démarrage ---------------------------------------------------------------------------------

def start_screen() -> None:
    """Split screen of the mockup: the indigo panel (title, introduction, features) next to the white form."""
    st.html(page_css(dark_mode()))
    if st.session_state.pop("outdated", False):
        st.info(OUTDATED, icon=":material/update:")
    with st.container(key="start-frame"):
        brand, form = st.columns([1.1, 1], gap=None)  # côte à côte ; empilées sur un écran de téléphone
        with brand, st.container(key="start-brand"):
            brand_panel()
        with form, st.container(key="start-form"):
            start_form()
    prewarm()  # après l'affichage : imports lourds en arrière-plan, aucun appel réseau


def brand_panel() -> None:
    """Left panel: title, introduction, scope and the five features (Publicités greyed when not configured)."""
    ads = web.ads_configured(start_registry(config.AD_ACCOUNT_ID, config.AD_ACCOUNT_MODE))
    st.html(brand_html(ads))  # HTML local : marges et interligne de la maquette, aucun texte collé au bord


def token_fingerprint() -> str:
    """Short fingerprint of FB_USER_TOKEN, used only as a cache key (never shown, the token is not kept).

    Returns:
        16 hexadecimal characters of its SHA-256.
    """
    return hashlib.sha256((config.FB_USER_TOKEN or "").encode()).hexdigest()[:16]


@st.cache_resource(show_spinner=False)
def account_preview(fingerprint: str) -> web.AccountPreview:
    """Names of the user and of the pages, read once in the background (GET me, GET me/accounts).

    Args:
        fingerprint: token_fingerprint() : a new token gives a new reading.

    Returns:
        The preview, filled by its thread.
    """
    return web.start_account_preview()


@st.fragment(run_every=REFRESH)
def watch_preview(preview: web.AccountPreview) -> None:
    """Draw the start screen again as soon as the names are read.

    Args:
        preview: The reading in progress.
    """
    if preview.done:
        st.rerun()


def start_form() -> None:
    """Right panel: who is connected, the page (a choice only with several pages and no FB_PAGE_ID),
    the dry-run switch, the main button and the sentence below it."""
    preview = account_preview(token_fingerprint())
    with st.container(horizontal=True, horizontal_alignment="right", key="start-theme"):
        dark_switch("start-dark")  # même réglage que le menu ⋮ de l'écran principal
    st.markdown("### Démarrer une session")
    with st.container(key="start-sub"):
        st.markdown(START_SUB)
    pages = st.session_state.get("pages") or (preview.pages if preview.needs_choice else None)
    page_id = None
    with st.container(key="field-page"):
        if pages:
            names = dict(pages)
            page_id = st.selectbox("Page", options=list(names), format_func=names.get, key="page_choice")
        else:
            page = preview.page_name() or st.session_state.get("page_name") or PAGE_UNKNOWN
            st.html(f'<p class="fa-field"><span class="fa-icon">storefront</span><b>{escape(page)}</b></p>')
        if preview.user_name:
            st.html(f'<p class="fa-field fa-quiet"><span class="fa-icon">person</span>'
                    f'Connecté en tant que {escape(preview.user_name)}</p>')
    with st.container(key="field-dry"):
        text, switch = st.columns([5, 1], vertical_alignment="center")
        text.html(f'<div class="fa-dry"><span class="fa-icon">science</span><div><b>Mode dry-run</b>'
                  f'<span class="fa-dry-desc">{DRY_RUN_NOTE}</span></div></div>')
        with switch, st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
            if DRY_KEY not in st.session_state:  # le dernier mode choisi (web_prefs.json)
                st.session_state[DRY_KEY] = prefs.load()["dry_run"]
            dry_run = st.toggle("Mode dry-run", key=DRY_KEY, label_visibility="collapsed", on_change=remember_dry_run)
    if st.button("Démarrer la session", type="primary", icon=":material/play_arrow:", width="stretch"):
        start(dry_run, page_id, preview.user_name)
    with st.container(key="start-note"):
        st.markdown(START_NOTE)
    if not preview.done:
        watch_preview(preview)


def start(dry_run: bool, page_id: str | None, user_name: str | None = None) -> None:
    """Open the session; a failure is shown in one short sentence, the detail folded below.

    Args:
        dry_run: State of the dry-run switch.
        page_id: Page chosen, when there are several.
        user_name: Name read on the start screen, shown in the header.
    """
    prefs.save(dry_run=dry_run)
    try:
        st.session_state.web = web.WebSession(dry_run=dry_run, page_id=page_id, user_name=user_name)
    except web.PageChoiceNeeded as exc:
        st.session_state.pages = exc.pages
        st.rerun()
    except ValueError as exc:
        st.error(f"Configuration invalide : {exc}", icon=":material/error:")
    except web.SessionError as exc:
        short, detail = web.split_error(str(exc))
        st.error(f"Impossible de démarrer : {short}", icon=":material/error:")
        if detail:
            with st.expander("Détails techniques", icon=":material/code:"):
                st.code(detail, language=None, wrap_lines=True)
    else:
        st.session_state.pop("pages", None)
        st.session_state.page_name = st.session_state.web.page_name  # affiché au prochain démarrage
        st.rerun()


# --- Barre latérale -------------------------------------------------------------------------------------

def sidebar(session: web.WebSession) -> None:
    """Two compact cards: the activity of the session (objects created) and the Groq quota.

    Args:
        session: Web session shown by the page.
    """
    with st.sidebar:
        with st.container(key="side-activity"):
            objects_panel(session)
        with st.container(key="side-quota"):
            quota_panel(session)


def model_label(model: str) -> str:
    """Name of a model in the quota panel: its full name, without the provider ("gpt-oss-120b").

    Args:
        model: Model name without its provider.

    Returns:
        The name.
    """
    return model or "modèle"


QUOTA_ESTIMATE = "estimation"  # décompte local : journaux de l'agent depuis minuit
QUOTA_EMPTY_ESTIMATE = ("Quota estimé épuisé. Groq peut encore accepter tes demandes ; s'il les refuse, l'agent "
                        "attendra qu'une partie du quota se libère (parfois plusieurs minutes).")
QUOTA_EMPTY_GROQ = "Quota du jour épuisé selon Groq : la prochaine demande sera mise en pause."


def quota_text(model: str, left: int, per_day: int, groq_at: str | None) -> str:
    """Text of a quota bar: the estimate, or Groq's own count after a 429 on the tokens per day.

    Args:
        model: Short model name.
        left: Tokens left.
        per_day: Daily quota.
        groq_at: "HH:MM" of Groq's count, or None for the local estimate.

    Returns:
        "gpt-oss-120b : 12 400 restants sur 200 000 (estimation)" or "… (Groq, 14:32)".
    """
    source = f"Groq, {groq_at}" if groq_at else QUOTA_ESTIMATE
    return f"{model_label(model)} : {short_number(left)} restants sur {short_number(per_day)} ({source})"


def quota_panel(session: web.WebSession) -> None:
    """Groq tokens left today, one progress bar per model with "restants" in words and the source of the count
    (local estimate, or Groq's count after a 429); a warning under a bar at 0 (the context of the next
    request stays in the "Détails" of each exchange).

    Args:
        session: Web session shown by the page.
    """
    section_title("Quota Groq")
    for model, left, per_day, groq_at in session.quota():
        st.progress(min(max(left / per_day, 0.0), 1.0) if per_day else 0.0,
                    text=quota_text(model, left, per_day, groq_at))
        if left <= 0:
            st.caption(f":material/warning: {QUOTA_EMPTY_GROQ if groq_at else QUOTA_EMPTY_ESTIMATE}")


def object_state(item: dict) -> str:
    """State badge of an object created or changed during the session.

    Args:
        item: Object of WebSession.objects_by_kind.

    Returns:
        "créé", "publiée", "envoyé", "changée", "modifié", "supprimé", "archivé" or "simulé".
    """
    return "simulé" if item["simulated"] else item["state"] or "créé"


KIND_ICONS = {"Post": "article", "Photo": "image", "Vidéo": "movie","Couverture": "panorama", "Photo de profil": "account_circle",
              "Commentaire": "comment", "Réponse": "reply", "Message": "chat", "Pièce jointe": "attach_file",
              "Produit": "shopping_bag", "Formulaire": "assignment", "Campagne": "campaign",
              "Ensemble de publicités": "view_list", "Publicité": "ads_click"}
NO_ACTIVITY = "Aucune action pour l'instant."


def object_html(kind: str, item: dict) -> str:
    """One line of a mini-card of the activity: icon of the type, name or excerpt, time and state badge.

    Args:
        kind: Type of the object ("Post", "Produit"…).
        item: Object of WebSession.objects_by_kind.

    Returns:
        The HTML (texts escaped, no script).
    """
    state = object_state(item)
    text = escape(item["text"] or kind)
    return (f'<div class="fa-mini"><span class="fa-icon">{KIND_ICONS.get(kind, "description")}</span>'
            f'<div class="fa-mini-body"><p class="fa-mini-title" title="{text}">{text}</p>'
            f'<p class="fa-mini-sub">{escape(kind)} · {escape(item["time"])}</p></div>'
            f'<span class="fa-badge-s fa-{STATE_BADGES.get(state, "gray")}">{state}</span></div>')


def objects_panel(session: web.WebSession) -> None:
    """Writes of the session (objects created, photos, cover, profile picture, comments, Messenger messages,
    products changed; sandbox campaigns included): one mini-card per object (icon, name,
    time, state badge) with its "ID" button; when empty, a grey history icon and one centred sentence.

    Args:
        session: Web session shown by the page.
    """
    section_title("Activité de la session")
    items = session.recent_objects()  # les plus récentes en haut
    if not items:
        st.html(f'<div class="fa-empty"><span class="fa-icon">history</span>{NO_ACTIVITY}</div>')
        return
    if st.session_state.get(ACTIVITY_SEEN) != len(items):  # nouvelle action : retour à la page 1
        st.session_state[ACTIVITY_SEEN] = len(items)
        st.session_state[ACTIVITY_PAGE] = 0
    pages = math.ceil(len(items) / ACTIVITY_PAGE_SIZE)
    page = min(max(int(st.session_state.get(ACTIVITY_PAGE, 0)), 0), pages - 1)
    first = page * ACTIVITY_PAGE_SIZE
    for number, item in enumerate(items[first:first + ACTIVITY_PAGE_SIZE], first):
        with st.container(key=f"obj-{number}"):
            st.html(object_html(item["kind"], item))
            if item["id"] and not item["simulated"]:  # dry-run : rien n'a été écrit, pas de bouton « ID »
                show_id(item["id"])  # « ID » : l'ID dans un bloc avec l'icône de copie de Streamlit
    if pages > 1:  # 5 lignes par page : le quota reste visible sous l'activité
        with st.container(key="activity-pages", horizontal=True, vertical_alignment="center", gap="small"):
            st.button("‹ Plus récentes", key="activity-newer", type="tertiary", disabled=page == 0,
                      on_click=set_activity_page, args=(page - 1,))
            st.html(f'<p class="fa-pages">page {page + 1} / {pages}</p>')
            st.button("Plus anciennes ›", key="activity-older", type="tertiary", disabled=page == pages - 1,
                      on_click=set_activity_page, args=(page + 1,))


ACTIVITY_PAGE_SIZE = 5
ACTIVITY_PAGE = "activity_page"  # page affichée du panneau d'activité (0 : les plus récentes)
ACTIVITY_SEEN = "activity_seen"  # nombre de lignes au dernier affichage : une nouvelle action ramène à la page 1


def set_activity_page(page: int) -> None:
    """Button « ‹ Plus récentes » or « Plus anciennes › » of the activity panel.

    Args:
        page: Page to show (0 = the most recent lines).
    """
    st.session_state[ACTIVITY_PAGE] = page


# --- Chat -----------------------------------------------------------------------------------------------

CHAT_KEY = "chat_text"  # clé de la zone de saisie : une suggestion y écrit sa demande
MENU_DRY_HELP = "Lectures réelles, aucune écriture envoyée. Indisponible pendant une demande."
# Rappel du mode sur chaque carte de confirmation
CONFIRM_DRY = ":orange-badge[:material/science: DRY-RUN : rien ne sera envoyé]"
CONFIRM_REAL = ":gray-badge[:material/bolt: Mode réel : envoyé à Facebook après confirmation]"
MENU_ACTIONS = (("help", ":material/help:", "Aide"), ("reset", ":material/restart_alt:", "Oublier l'historique"),
                ("end", ":material/logout:", "Terminer la session"))


def header(session: web.WebSession) -> None:
    """Compact header: "Agent · <page>", "Connecté en tant que <nom>" in small, and our own ⋮ menu at the
    place of Streamlit's (Aide, Oublier l'historique, Terminer la session); in DRY-RUN only, the orange banner.

    Args:
        session: Web session shown by the page.
    """
    # fixé en haut pendant le défilement (CSS sticky, conteneur app-top) : l'en-tête, une ligne qui ne s'empile
    # jamais, même sur un téléphone, puis le bandeau DRY-RUN quand le dry-run est actif
    with st.container(key="app-top"):
        header_row(session)
        if session.dry_run:
            st.html(f'<p class="fa-dryrun">{DRY_RUN_BANNER}</p>')
    open_dialog(session)


def header_row(session: web.WebSession) -> None:
    """Row of the header: "Agent · <page>", "Connecté en tant que <nom>" and the ⋮ menu.

    Args:
        session: Web session shown by the page.
    """
    with st.container(key="app-head", horizontal=True, vertical_alignment="center", gap="small"):
        user = (f'<p class="fa-head-user">Connecté en tant que {escape(session.user_name)}</p>'
                if session.user_name else "")
        st.html(f'<div class="fa-head"><p class="fa-head-title">Agent · {escape(session.page_name)}</p>{user}</div>')
        with st.container(horizontal=True, horizontal_alignment="right", key="head-menu", width="content"):
            if st.session_state.get(DIALOG_KEY):  # une fenêtre de confirmation s'ouvre : le menu se ferme
                st.session_state[MENU_KEY] = False
            with st.popover(":material/more_vert:", help="Menu", key=MENU_KEY, on_change="rerun"):
                for action, icon, label in MENU_ACTIONS:
                    # pendant une demande ou une confirmation : seul « Terminer la session » reste possible
                    if st.button(label, icon=icon, key=f"menu-{action}", width="stretch",
                                 disabled=(session.busy or session.pending is not None) and action != "end"):
                        header_action(session, action)
                dark_switch("menu-dark")
                # pas pendant une demande ni une confirmation : le mode d'une écriture affichée ne change jamais
                st.session_state["menu-dry"] = session.dry_run  # toujours le mode réel de la session
                st.toggle("Mode dry-run", key="menu-dry", on_change=switch_mode,
                          args=(session,), disabled=session.busy or session.pending is not None,
                          help=MENU_DRY_HELP)


DIALOG_KEY = "open_dialog"  # fenêtre de confirmation ouverte : "reset", "end", "real" ou "dry"
MENU_KEY = "head-popover"  # état ouvert / fermé du menu ⋮ (fermé quand une fenêtre s'ouvre)
RESET_QUESTION = "Oublier l'historique de la conversation ? L'agent ne se souviendra plus des échanges précédents."
END_QUESTION = ("Terminer la session ? Tu reviendras à l'écran de démarrage, et la conversation en cours sera "
                "effacée.")
REAL_QUESTION = "Passer en mode réel ? Les actions que tu confirmeras seront envoyées à Facebook."
DRY_QUESTION = "Passer en mode dry-run ? Les actions seront simulées, rien ne sera envoyé à Facebook."


def close_dialog() -> None:
    """Forget the open window (« Annuler », a click outside it or its cross): nothing else changes."""
    st.session_state.pop(DIALOG_KEY, None)


def dialog_buttons(label: str, icon: str, key: str) -> tuple[bool, bool]:
    """The two buttons of a confirmation window: the action (primary) and « Annuler ».

    Args:
        label: Text of the action button (« Oublier », « Terminer »).
        icon: Its Material icon.
        key: Prefix of the keys of the buttons.

    Returns:
        (action clicked, « Annuler » clicked).
    """
    left, right = st.columns(2)
    confirmed = left.button(label, key=f"{key}-yes", type="primary", icon=icon, width="stretch")
    cancelled = right.button("Annuler", key=f"{key}-no", icon=":material/close:", width="stretch")
    return confirmed, cancelled


@st.dialog("Oublier l'historique", on_dismiss=close_dialog)
def reset_dialog(session: web.WebSession) -> None:
    """Window of « Oublier l'historique »: « Oublier » empties the history, « Annuler » changes nothing.

    Args:
        session: Web session shown by the page.
    """
    st.markdown(RESET_QUESTION)
    confirmed, cancelled = dialog_buttons("Oublier", ":material/restart_alt:", "reset")
    if confirmed:
        close_dialog()
        session.reset()
        st.rerun()
    if cancelled:
        close_dialog()
        st.rerun()


@st.dialog("Terminer la session", on_dismiss=close_dialog)
def end_dialog(session: web.WebSession) -> None:
    """Window of « Terminer la session »: « Terminer » closes it (request cancelled, tokens forgotten) and goes
    back to the start screen, « Annuler » changes nothing.

    Args:
        session: Web session shown by the page.
    """
    st.markdown(END_QUESTION)
    confirmed, cancelled = dialog_buttons("Terminer", ":material/logout:", "end")
    if confirmed:
        close_dialog()
        session.close()
        st.session_state.pop("web", None)
        st.rerun()
    if cancelled:
        close_dialog()
        st.rerun()


def change_mode(session: web.WebSession, dry_run: bool) -> None:
    """Button of a mode window: the new mode for the session, kept for the next start (web_prefs.json).

    Args:
        session: Web session shown by the page.
        dry_run: True for dry-run, False for the real mode.
    """
    close_dialog()
    if session.set_dry_run(dry_run):  # refusé si une demande a commencé : rien ne change
        prefs.save(dry_run=dry_run)
    st.rerun()


@st.dialog("Mode réel", on_dismiss=close_dialog)
def real_dialog(session: web.WebSession) -> None:
    """Window of the switch towards the real mode: « Passer en mode réel » or « Annuler » (mode unchanged).

    Args:
        session: Web session shown by the page.
    """
    st.markdown(REAL_QUESTION)
    confirmed, cancelled = dialog_buttons("Passer en mode réel", ":material/bolt:", "real")
    if confirmed:
        change_mode(session, False)
    if cancelled:
        close_dialog()
        st.rerun()


@st.dialog("Mode dry-run", on_dismiss=close_dialog)
def dry_dialog(session: web.WebSession) -> None:
    """Window of the switch towards dry-run: « Passer en dry-run » or « Annuler » (mode unchanged).

    Args:
        session: Web session shown by the page.
    """
    st.markdown(DRY_QUESTION)
    confirmed, cancelled = dialog_buttons("Passer en dry-run", ":material/science:", "dry")
    if confirmed:
        change_mode(session, True)
    if cancelled:
        close_dialog()
        st.rerun()


def open_dialog(session: web.WebSession) -> None:
    """Draw the confirmation window chosen in the ⋮ menu, at every run until it is answered or dismissed.

    « Oublier l'historique » and a change of mode are dropped when a request starts meanwhile (the history
    and the mode must not change under it); « Terminer la session » stays possible during a request.

    Args:
        session: Web session shown by the page.
    """
    which = st.session_state.get(DIALOG_KEY)
    if which in ("reset", "real", "dry") and (session.busy or session.pending is not None):
        close_dialog()
    elif which == "real":
        real_dialog(session)
    elif which == "dry":
        dry_dialog(session)
    elif which == "reset":
        reset_dialog(session)
    elif which == "end":
        end_dialog(session)


def header_action(session: web.WebSession, action: str) -> None:
    """Run a button of the header: the help, or the window that confirms « Oublier l'historique » or
    « Terminer la session » (nothing is erased nor closed before its button).

    Args:
        session: Web session shown by the page.
        action: "help", "reset" or "end".
    """
    if action == "help":
        session.submit("/aide")
    else:
        st.session_state[DIALOG_KEY] = action
    st.rerun()


def fill_input(text: str) -> None:
    """Write a suggestion into the chat input, without sending it (callback of a suggestion card).

    st.chat_input (1.66) takes a text set in st.session_state before it is drawn: the user can then
    change it and send it with Entrée.

    Args:
        text: Request of the suggestion (a read in full; a write asks the agent for the details).
    """
    st.session_state[CHAT_KEY] = text


CARDS_PER_ROW = 3  # titres complets, jamais coupés
SUGGEST_ROW_PX = 72  # hauteur d'une ligne de cartes (64 px) et de l'espace en dessous (8 px)


def suggestions_height(session: web.WebSession) -> int:
    """Height of the tabs of the "Suggestions" window: the tab with the most suggestions sets it.

    Args:
        session: Web session shown by the page.

    Returns:
        Pixels, so the window keeps the same size whatever the tab.
    """
    most = max((len(items) for items in session.suggestions().values()), default=0)
    return math.ceil(most / CARDS_PER_ROW) * SUGGEST_ROW_PX


def suggestions(session: web.WebSession, key: str, fixed_height: bool = False) -> None:
    """Suggestions: underlined tabs by domain (active domains only, with icons), then a grid of cards
    (icon, bold title; description as tooltip). A click fills the chat input; nothing is sent.

    Args:
        session: Web session shown by the page.
        key: Prefix of the keys of the widgets.
        fixed_height: True in the "Suggestions" window: every tab gets the height of the fullest one.
    """
    groups = session.suggestions()
    if not groups:
        return
    if fixed_height:
        st.html(f'<style>.st-key-suggest-{key} [data-testid="stTabPanel"] '
                f'{{ min-height: {suggestions_height(session)}px; }}</style>')
    with st.container(key=f"suggest-{key}"):
        tabs = st.tabs([f"{session.group_icon(group)} {group}" for group in groups])
        for group_number, (tab, (group, items)) in enumerate(zip(tabs, groups.items())):
            with tab:
                for start_at in range(0, len(items), CARDS_PER_ROW):
                    row = items[start_at:start_at + CARDS_PER_ROW]
                    for column, (number, (label, text)) in zip(st.columns(CARDS_PER_ROW), enumerate(row, start_at)):
                        icon, description = session.suggestion_card(label)
                        # carte compacte sur une ligne : icône et titre ; la description en infobulle
                        column.button(label, key=f"sugcard-{key}-{group_number}-{number}", icon=icon,
                                      help=description, on_click=fill_input, args=(text,), disabled=session.busy,
                                      width="stretch")


HELP_DOMAINS = {"Page": "Posts, commentaires, photos et vidéos de la page.",
                "Messenger": "Lire les conversations des clients et leur répondre.",
                "Catalogue": "Produits, prix et promotions, collections et flux.",
                "Lead Ads": "Formulaires de contact et leads, données personnelles masquées.",
                "Publicités": "Campagnes, ensembles et publicités en pause, booster un post."}
ADS_HELP_NOTES = {"sandbox": "Compte sandbox, aucune dépense.",
                  "no_payment": "Compte sans moyen de paiement, aucune dépense."}


def help_html(session: web.WebSession) -> str:
    """Help in the style of the start screen: one compact card per active domain, then short rules with icons.

    Args:
        session: Web session shown by the page.

    Returns:
        The HTML (texts of this file only, no script).
    """
    cards = []
    for title, icon, labels in session.domain_groups():
        if not labels:  # domaine non configuré : pas de carte
            continue
        sentence = HELP_DOMAINS[title]
        if title == "Publicités":
            sentence += " " + ADS_HELP_NOTES.get(session.registry.ads_mode, ADS_HELP_NOTES["sandbox"])
        cards.append(f'<div class="fa-help-card"><span class="fa-icon">{material_name(icon)}</span>'
                     f'<div><b>{title}</b><span>{sentence}</span></div></div>')
    rules = (("front_hand", f"Chaque écriture attend ta confirmation ({CONFIRM_MINUTES} min sans réponse : refus)."),
             ("filter_3", f"Au plus {session.agent.executor.max_writes} actions par demande."),
             ("science", "Dry-run, au démarrage : lectures réelles, aucune écriture envoyée."),
             ("lightbulb", "Suggestions au-dessus de la zone de saisie ; menu ⋮ : aide, oublier l'historique, "
                           "mode sombre, fin de session."))
    items = "".join(f'<li><span class="fa-icon">{icon}</span>{text}</li>' for icon, text in rules)
    return (f'<div class="fa-help"><div class="fa-help-grid">{"".join(cards)}</div>'
            f'<ul class="fa-help-rules">{items}</ul></div>')


def close_help(turn: web.Turn) -> None:
    """Button "Fermer l'aide": the help is no longer drawn (the exchange stays in the list).

    Args:
        turn: The help.
    """
    turn.hidden = True


def show_help(session: web.WebSession, turn: web.Turn, index: int) -> None:
    """Help: cards of the active domains, short rules, and a button to close it.

    Args:
        session: Web session shown by the page.
        turn: The help (closed by its button).
        index: Position of the help in the chat (keys of its buttons).
    """
    with st.container(key=f"card-help-{index}"):
        st.markdown("#### :material/help: Aide")
        st.html(help_html(session))
        st.button("Fermer l'aide", key=f"help-close-{index}", icon=":material/close:", on_click=close_help,
                  args=(turn,))


def show_command(session: web.WebSession, turn: web.Turn, index: int) -> None:
    """/aide and /reset: a system notification (toast) and a discreet line, never a message of the user.

    Args:
        session: Web session shown by the page.
        turn: The command.
        index: Its position in the chat.
    """
    if not turn.notified:
        turn.notified = True
        st.toast(turn.answer if turn.kind == "reset" else "Aide affichée.", duration=TOAST_SECONDS,
                 icon=":material/restart_alt:" if turn.kind == "reset" else ":material/help:")
    if turn.kind == "help":
        if not turn.hidden:
            show_help(session, turn, index)
    else:
        st.caption(":material/restart_alt: Historique vidé : la conversation repart de zéro "
                   "(les objets créés restent listés).")


def show_confirmation(session: web.WebSession, confirmation: web.Confirmation, key: str) -> None:
    """Card of a write: color of its level, action as title, parameters as a table, full text folded,
    then the buttons or the outcome.

    Args:
        session: Web session shown by the page.
        confirmation: The confirmation to show.
        key: Prefix of the keys of its buttons.
    """
    view = confirmation.view
    color, icon, css = LEVELS.get(view.level or "", ("gray", ":material/help:", "other"))
    with st.container(border=True, key=f"card-{css}-{key}"):
        st.markdown(f":{color}-badge[{icon} {view.level or 'ACTION'}]"
                    + "".join(f" :gray-badge[:material/inventory_2: {banner}]" for banner in view.banners)
                    + f" {CONFIRM_DRY if confirmation.dry_run else CONFIRM_REAL}")
        st.markdown(f"#### {view.action[:1].upper()}{view.action[1:]}")
        if view.tool:
            st.caption(view.tool)
        if view.rows:
            st.table({"Paramètre": [k for k, _ in view.rows], "Valeur": [v for _, v in view.rows]})
        for note in view.notes:
            st.markdown(f"**{note}**")
        if view.consequence:
            st.markdown(f"**{view.level}** : {view.consequence}")
        with st.expander("Texte complet de la confirmation", icon=":material/notes:"):
            st.code(confirmation.text, language=None, wrap_lines=True)
        if confirmation.outcome is None and confirmation is session.pending:
            left, right = st.columns(2)
            if left.button("Confirmer", key=f"{key}-yes", type="primary", icon=":material/check:", width="stretch"):
                session.answer(True)
                st.rerun()
            if right.button("Refuser", key=f"{key}-no", icon=":material/close:", width="stretch"):
                session.answer(False)
                st.rerun()
            st.caption(f"Sans réponse en {CONFIRM_MINUTES} min : refus.")
        elif confirmation.outcome == "timeout":
            st.warning(confirmation.label, icon=":material/timer_off:")
        elif confirmation.outcome == "accepted":
            st.caption(f":material/check_circle: {confirmation.label}")
        elif confirmation.outcome:
            st.caption(confirmation.label)


TICK = 1.0  # secondes entre deux mises à jour du bloc de progression (compte à rebours, temps écoulé)
CONFIRM_ICON = ":material/front_hand:"  # attente d'une confirmation : ni spinner, ni coche
DONE_ICON, FAILED_ICON = ":material/check:", ":material/close:"  # bloc replié « Détails » : coche, ou croix si erreur


def progress_label(session: web.WebSession, turn: web.Turn) -> str:
    """Title of the progress block: the step in plain French and the time elapsed ("Lecture des posts… · 4 s").

    Args:
        session: Web session shown by the page.
        turn: The running request.

    Returns:
        The title.
    """
    elapsed = session.elapsed(turn)
    return f"{session.phase(turn)} · {elapsed}" if elapsed else session.phase(turn)


@st.fragment(run_every=TICK)
def show_progress(session: web.WebSession, turn: web.Turn, index: int) -> None:
    """Progress of the running request, drawn again every second: a spinner (or the hand while a confirmation
    waits), the step in plain French, the time elapsed, the steps done, the Groq pause as a countdown with
    its bar, and the cancel button.

    st.status is never used as a context manager here: leaving the "with" block would mark it complete (check mark)
    while the request still runs.

    Args:
        session: Web session shown by the page.
        turn: The running request.
        index: Its position in the chat.
    """
    if turn.done:  # réponse arrivée entre deux mises à jour : la page entière est redessinée
        st.rerun()
    label = progress_label(session, turn)
    box = (st.expander(label, expanded=True, icon=CONFIRM_ICON) if session.pending is not None
           else st.status(label, state="running", expanded=True))
    for step in turn.steps():
        box.text(step)
    pause = session.pause()
    if pause:
        left, total, reason = pause
        box.progress(min(max((total - left) / total, 0.0), 1.0) if total else 0.0,
                     text=f"Pause Groq ({reason}) : {web.duration(left)}…")
    # rappel au clic (avant tout le reste) : la confirmation affichée est annulée, jamais lue comme un refus
    box.button("Annuler la demande", key=f"cancel-{index}", icon=":material/cancel:", on_click=session.cancel)


def show_turn(session: web.WebSession, turn: web.Turn, index: int) -> None:
    """One exchange: the request, its confirmations, then the progress or the answer and its folded blocks.

    Args:
        session: Web session shown by the page.
        turn: The exchange.
        index: Its position in the chat (keys of its buttons).
    """
    if turn.command:
        show_command(session, turn, index)
        return
    with st.chat_message("user", avatar=":material/person:"), st.container(key=f"umsg-{index}"):
        st.text(turn.request)  # la clé repère la bulle de l'utilisatrice pour le mode sombre
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        for number, confirmation in enumerate(turn.confirmations):
            show_confirmation(session, confirmation, f"c{index}-{number}")
        if not turn.done:
            show_progress(session, turn, index)
            return
        if turn.answer:  # vide quand la carte d'une liste vide dit déjà tout
            st.markdown(turn.answer)
        carded = set()
        for number, cardset in enumerate(turn.cardsets):
            show_cardset(session, cardset, f"r{index}-{number}")
            carded |= {card.id for card in cardset.cards if card.id}
        for kind, object_id in turn.copyable_ids():
            if object_id in carded:  # déjà sur sa carte, avec son bouton « ID »
                continue
            label, value = st.columns([1, 3], vertical_alignment="center")
            label.caption(kind)
            value.code(object_id, language=None)  # bouton Copier intégré au bloc
        if turn.leads:
            with st.expander(LEADS_TITLE, icon=":material/lock:"):
                st.caption(LEADS_NOTE)
                st.code("\n".join(turn.leads), language=None, wrap_lines=True)
        if turn.details or turn.status_line or turn.failed:
            # le bloc de progression replié : coche (ou croix en cas d'erreur), étapes, éléments reçus, contexte, durée
            with st.expander("Détails", icon=FAILED_ICON if turn.failed else DONE_ICON, expanded=False):
                if turn.details:
                    st.code("\n".join(turn.details), language=None, wrap_lines=True)
                if turn.status_line:
                    st.caption(turn.status_line)
                if session.elapsed(turn):
                    st.caption(f"Durée de la demande : {session.elapsed(turn)}")


ID_ICON = ":material/tag:"  # petit bouton « ID » des cartes


def show_id(object_id: str, where=None) -> None:
    """Small "ID" button of a card: a popover with the ID in st.code, copied with Streamlit's own copy icon
    (no script: a script drawn by st.html could not reach the clipboard).

    Args:
        object_id: ID of the object (checked by cards.safe_id).
        where: Container of the button (a cell of a table), or None for the current container.
    """
    with (where or st).popover("ID", icon=ID_ICON):
        st.code(object_id, language=None)


def thumb_html(image: str | None, icon: str = "image") -> str:
    """Picture of a card in a grey frame with an icon: the frame stays visible if the picture does not load.

    Args:
        image: https URL of the picture (cards.safe_url), or None.
        icon: Material icon drawn in the frame.

    Returns:
        The HTML (no script: the frame is behind the picture).
    """
    picture = f'<img src="{escape(image)}" alt="" loading="lazy">' if image else ""
    return f'<div class="fa-thumb"><span class="fa-icon">{icon}</span>{picture}</div>'


def list_card_html(card) -> str:
    """One card of a list (posts): picture, text, date and counts, link to Facebook. Texts are escaped.

    Args:
        card: cards.Card.

    Returns:
        The HTML (no script).
    """
    picture = thumb_html(card.image) if card.image else ""
    badges = f'<p class="fa-badges">{badges_html(card)}</p>' if card.badges else ""
    return (f'<div class="fa-rcard">{picture}<div class="fa-rbody"><p class="fa-rtext">{escape(card.title)}</p>'
            f'{badges}<p class="fa-rsub">{escape(card.subtitle)}</p>{link_html(card)}</div></div>')


GRID_PER_ROW = 4


def link_html(card) -> str:
    """Link of a card to Facebook or the Meta interface (opens a new tab), or "".

    Args:
        card: cards.Card.

    Returns:
        The HTML.
    """
    if not card.link:
        return ""
    return (f'<a class="fa-rlink" href="{escape(card.link)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="fa-icon">open_in_new</span>{escape(card.link_label)}</a>')


BADGE_COLORS = ("green", "red", "orange", "blue", "gray")


def badges_html(card) -> str:
    """State badges of a card (En stock, En pause…), or "".

    Args:
        card: cards.Card.

    Returns:
        The HTML.
    """
    return "".join(f'<span class="fa-badge-s fa-{color if color in BADGE_COLORS else "gray"}">{escape(label)}</span>'
                   for label, color in card.badges)


def price_html(card) -> str:
    """Price of a product: the promotional price in bold and the usual price struck out, or the price alone.

    Args:
        card: cards.Card (columns "price" and "sale_price").

    Returns:
        The HTML, or "".
    """
    price, sale = card.columns.get("price"), card.columns.get("sale_price")
    if sale:
        return f'<p class="fa-price"><b>{escape(sale)}</b> <s>{escape(price or "")}</s></p>'
    return f'<p class="fa-price"><b>{escape(price)}</b></p>' if price else ""


def grid_card_html(card, icon: str) -> str:
    """One card of a grid (photos, albums, videos, products): thumbnail in its frame, title, price,
    badges, date, link.

    Args:
        card: cards.Card.
        icon: Material icon of the frame (shown when there is no picture or it does not load).

    Returns:
        The HTML (no script, texts escaped).
    """
    title = f'<p class="fa-rtext">{escape(card.title)}</p>' if card.title else ""
    subtitle = f'<p class="fa-rsub">{escape(card.subtitle)}</p>' if card.subtitle else ""
    badges = f'<p class="fa-badges">{badges_html(card)}</p>' if card.badges else ""
    return (f'<div class="fa-gcard">{thumb_html(card.image, icon)}{title}{price_html(card)}{badges}'
            f'{subtitle}{link_html(card)}</div>')


def chat_html(cards) -> str:
    """Messages of a conversation as bubbles: the client on the left, the page on the right (texts escaped).

    Args:
        cards: cards.Card of messages_cards (columns["role"]).

    Returns:
        The HTML (no script).
    """
    bubbles = "".join(f'<div class="fa-bubble fa-{"mine" if card.columns.get("role") == "page" else "theirs"}">'
                      f'<p class="fa-rtext">{escape(card.title)}</p><p class="fa-rsub">{escape(card.subtitle)}</p></div>'
                      for card in cards)
    return f'<div class="fa-thread">{bubbles}</div>'


def show_table(cardset, key: str) -> None:
    """Campaigns, ad sets or ads as a table: its columns, the status badge and the "ID" button on each row,
    and the link to Ads Manager once below (never for a sandbox account).

    Args:
        cardset: cards.CardSet with layout "table".
        key: Prefix of the keys of its containers.
    """
    headers = list(cardset.cards[0].columns)
    widths = [3] + [2] * (len(headers) - 1) + [1.6, 1.6]
    with st.container(key=f"rcard-{key}-table"):
        for column, header in zip(st.columns(widths), [*headers, "Statut", ""]):
            column.html(f'<p class="fa-th">{escape(header)}</p>')
        for card in cardset.cards:
            cells = st.columns(widths, vertical_alignment="center")
            for column, value in zip(cells, card.columns.values()):
                column.html(f'<p class="fa-td">{escape(value)}</p>')
            cells[len(headers)].html(f'<p class="fa-badges">{badges_html(card)}</p>')
            if card.id:
                show_id(card.id, cells[-1])
        if cardset.cards[0].link:
            st.html(link_html(cardset.cards[0]))


def shown_cards(cardset, key: str) -> int:
    """Number of cards of a list shown now: all, or page_size more after each "Voir plus" (Lead Ads forms).

    Args:
        cardset: cards.CardSet.
        key: Prefix of the keys of its widgets.

    Returns:
        The number of cards to draw.
    """
    if not cardset.page_size:
        return len(cardset.cards)
    return min(st.session_state.get(f"shown-{key}", cardset.page_size), len(cardset.cards))


def show_more(key: str, count: int) -> None:
    """Show more cards of a list already received ("Voir plus" of the Lead Ads forms).

    Args:
        key: Prefix of the keys of the card set.
        count: Number of cards to show from now on.
    """
    st.session_state[f"shown-{key}"] = count


def show_cardset(session: web.WebSession, cardset, key: str) -> None:
    """Cards of one result: the empty message, the cards, "Voir plus" when more items exist.

    Args:
        session: Web session shown by the page.
        cardset: cards.CardSet.
        key: Prefix of the keys of its widgets.
    """
    if not cardset.cards:
        st.info(cardset.empty, icon=":material/inbox:")
        return
    if cardset.note:
        st.caption(cardset.note)
    if cardset.layout == "chat":
        with st.container(key=f"rcard-{key}-chat"):
            st.html(chat_html(cardset.cards))
    elif cardset.layout == "table":
        show_table(cardset, key)
    elif cardset.layout == "grid":
        icon = THUMB_ICONS.get(cardset.tool, "image")
        for start_at in range(0, len(cardset.cards), GRID_PER_ROW):
            row = cardset.cards[start_at:start_at + GRID_PER_ROW]
            for column, (number, card) in zip(st.columns(GRID_PER_ROW), enumerate(row, start_at)):
                with column.container(key=f"rcard-{key}-{number}"):
                    st.html(grid_card_html(card, icon))
                    if card.id:
                        show_id(card.id)
    else:
        shown = shown_cards(cardset, key)
        for number, card in enumerate(cardset.cards[:shown]):
            with st.container(key=f"rcard-{key}-{number}"):
                st.html(list_card_html(card))
                if card.id:
                    show_id(card.id)
        if shown < len(cardset.cards):  # cartes déjà reçues : montrées sans nouvelle demande
            st.button("Voir plus", key=f"{key}-more", icon=":material/expand_more:", on_click=show_more,
                      args=(key, shown + cardset.page_size))
            return
    if cardset.more and cardset.more_request:
        st.button("Voir plus", key=f"{key}-more", icon=":material/expand_more:",  # sans infobulle : elle
                  on_click=session.submit, args=(cardset.more_request,), disabled=session.busy)  # cachait le bouton « ID »


def chat_screen(session: web.WebSession) -> None:
    """Header, notices, suggestions (open until the first request, then folded), exchanges and chat input;
    reads the running request again.

    Args:
        session: Web session shown by the page.
    """
    st.html(page_css(dark_mode()))
    sidebar(session)
    header(session)
    for notice in session.notices:
        st.info(notice, icon=":material/info:")
    if not any(not turn.command for turn in session.turns):
        suggestions(session, "example")
    else:  # après le premier message : un bouton fixé juste au-dessus de la zone de saisie
        with st.bottom, st.container(key="suggest-button"):
            with st.popover("Suggestions", icon=":material/lightbulb:"):
                suggestions(session, "example", fixed_height=True)
    for index, turn in enumerate(session.turns):
        show_turn(session, turn, index)
    text = st.chat_input("Écris une demande…", key=CHAT_KEY, disabled=session.busy)
    if text and session.submit(text):
        st.rerun()
    if session.busy:
        watch(session, progress(session))


def progress(session: web.WebSession) -> tuple:
    """What the page shows of the running request: it is drawn again when this changes.

    Args:
        session: Web session shown by the page.

    Returns:
        A tuple that changes with each change of the page (answer, confirmation, notice); the steps, the
        pause and the time elapsed are drawn by the progress block itself (show_progress, every second).
    """
    turn = session.turns[-1] if session.turns else None
    return (session.busy, len(session.turns), id(session.pending), len(session.notices),
            (turn.done, [c.outcome for c in turn.confirmations]) if turn else None)


@st.fragment(run_every=REFRESH)
def watch(session: web.WebSession, shown: tuple) -> None:
    """Read the request every REFRESH seconds; draw the page again when it progressed (answer, confirmation…).

    Args:
        session: Web session shown by the page.
        shown: progress(session) when the page was drawn.
    """
    if progress(session) != shown:
        st.rerun()


def current_session() -> web.WebSession | None:
    """The session of this browser tab, or None.

    A session created by a previous version of the code (Streamlit reloads the modules when a file
    changes, but the object kept in session_state keeps its old class) is closed: its methods may not
    match the page any more (e.g. quota() returning two values instead of three).

    Returns:
        The WebSession, or None (start screen).
    """
    session = st.session_state.get("web")
    if session is None or isinstance(session, web.WebSession):
        return session
    try:
        session.close()  # journal fermé, tokens oubliés
    except Exception:  # ancienne version : la fermeture ne doit pas empêcher l'écran de démarrage
        pass
    del st.session_state["web"]
    st.session_state.outdated = True
    return None


st.set_page_config(page_title=APP_TITLE, page_icon=":material/smart_toy:", layout="wide",
                   initial_sidebar_state="auto")  # barre latérale repliée par défaut sur un petit écran
active = current_session()
if active is not None:
    chat_screen(active)
else:
    start_screen()

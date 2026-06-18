"""i18n_strings.py — Master UI string dictionary + batch translation.

Every user-visible UI string lives here as a flat key→English dict.
The `/i18n/strings?lang=xx` endpoint translates the whole dict via the
MT adapter (cached to disk after first call, free forever after).

Keys are namespaced by surface:  nav.almanac, hero.title, search.placeholder, etc.
Pages reference them via `data-i18n="key"` attributes; the shared `i18n.js`
module loads the dict once and replaces text in-place.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).parent.parent
_CACHE_DIR = _REPO / "data" / "i18n_cache"

# ── Master English strings ─────────────────────────────────────────────
# One flat dict. Keys are dot-namespaced. Values are the English text
# exactly as it appears in the HTML. Add new strings here as pages grow.

STRINGS: Dict[str, str] = {
    # ── Nav ──
    "nav.almanac":          "Almanac",
    "nav.library":          "Library",
    "nav.mcp":              "MCP",
    "nav.connect":          "Connect →",
    "nav.live":             "live",
    "nav.curriculum":       "Curriculum",
    "nav.walk":             "Walk",
    "nav.scribe":           "Scribe",
    "nav.daily":            "Daily",
    "nav.today":            "Today",
    "nav.bibles":           "Bibles",
    "nav.shepherd":         "Shepherd",
    "nav.apothecary":       "Apothecary",
    "nav.parable":          "Parable",
    "nav.training":         "Training",
    "nav.places":           "Places",
    "nav.receipts":         "Receipts",
    "nav.misalignments":    "Misalignments",
    "nav.atlas":            "Atlas",
    "nav.encyclopedia":     "Encyclopedia",
    "nav.chronicle":        "Chronicle",
    "nav.canon":            "Canon",
    "nav.fieldkit":         "Field Kit",
    "nav.archetypes":       "Archetypes",
    "nav.packets":          "Packets",
    "nav.run":              "Run",
    "nav.benchmark":        "Benchmark",
    "nav.how_it_works":     "How it works",
    "nav.verifiers":        "Verifiers",
    "nav.install":          "Install",

    # ── Landing / Hero ──
    "hero.eyebrow":         "The Concordance · narrowhighway.com",
    "hero.today_link":      "Today's devotion → Mind, Body, Spirit",
    "hero.title":           "Look up anything.",
    "hero.title_2":         "The engine finds what's true.",
    "hero.subtitle":        "A free, Christ-anchored concordance. Scripture, science, history, health, parables, protocols — {entries} entries across {bibles} Bibles and {domains} verified domains. No AI opinions. No affiliate links. Free.",

    # ── Three doors ──
    "door.carry_title":     "I'm carrying something",
    "door.carry_desc":      "Describe a hard situation. The Shepherd walks you through it with Scripture, patterns, and four gates.",
    "door.lookup_title":    "I want to look something up",
    "door.lookup_desc":     "Search the whole concordance. Health claims, Bible verses, folk wisdom, history — verified, with sources.",
    "door.teach_title":     "I want to teach my child",
    "door.teach_desc":      "66 units across phonics, math, reading, writing, science, social studies, Bible. Free. No accounts.",

    # ── Work area (the current landing page, index.html) ──
    "work.eyebrow":          "Bring anything · it knows what to do",
    "work.title":            "The work area.",
    "work.tagline":          "A note becomes a list. A message becomes a ready draft. A claim is run through the engine — verdict, trail, and a seal anyone can re-check. It knows what to do, and it is yours to keep.",
    "work.input_placeholder": "Write a journal entry · search the concordance · check a claim · draft a message · pull up your settings — or drop a file here. It goes where it should.",
    "work.bring_button":     "Bring it →",
    "work.explore":          "Free. No login, no ads, nothing tracked. The engine verifies; the assistant only drafts — and says so.",
    "work.what_is_this":     "What is this? — the whole story →",
    "work.link_learn":       "Learn anything →",
    "work.link_kept":        "Your things →",
    "work.link_brain":       "The engine as a brain →",
    "work.link_breath":      "The map, by what proves it →",
    "work.link_mcp":         "For developers & AI →",

    # ── Search ──
    "search.placeholder":   'Search — "does ginger help nausea?" · "John 14:6" · "what does agape mean?"',
    "search.button":        "Search →",
    "search.tools_toggle":  "+ pick tools to narrow",
    "search.save_lane":     "save this lane →",
    "search.try_label":     "Try:",
    "search.verify_label":  "Click one — real engine, no AI, instant",
    "search.no_results":    "Not in the keeping yet. Crafting a seed…",
    "search.results_for":   "You asked",
    "search.matches":       "matches",
    "search.enter_hint":    "Enter ↵ for all {n} results",
    "search.your_lanes":    "your lanes:",

    # ── Offline banner ──
    "offline.title":        "Engine offline",
    "offline.message":      "The engine is not responding right now. You can still type into the cards below — anything you write will be saved locally on your device and you can try again when the engine is back.",

    # ── Scribe section ──
    "scribe.title":         "Write",
    "scribe.placeholder":   "Write anything. A prayer, a journal entry, a question you're wrestling with. The engine will listen.",
    "scribe.submit":        "Send to the Scribe →",
    "scribe.reach_label":   "The keeping already has",
    "scribe.related_label": "Related in the keeping",
    "scribe.saved":         "Saved. The Scribe has it.",

    # ── Coach / Walk ──
    "walk.title":           "Walk a situation",
    "walk.placeholder":     "Describe what you're carrying…",
    "walk.submit":          "Walk this →",

    # ── Apothecary ──
    "apothecary.title":     "Apothecary",
    "apothecary.subtitle":  "A compound for what you carry",
    "apothecary.placeholder": "What are you carrying?",
    "apothecary.submit":    "Compound a remedy →",

    # ── Common labels ──
    "common.confirmed":     "Confirmed",
    "common.mismatch":      "Popularly believed, but wrong",
    "common.mixed":         "Mixed — partly true",
    "common.obsolete":      "Obsolete",
    "common.concordant":    "Concordant",
    "common.discovered":    "Discovered",
    "common.verdict":       "Verdict",
    "common.domains":       "Domains",
    "common.source":        "Source",
    "common.scripture":     "Scripture",
    "common.proverb":       "Proverb",
    "common.protocol":      "Protocol",
    "common.training":      "Training",
    "common.mind":          "Mind",
    "common.parable":       "Parable",
    "common.body":          "Body",
    "common.philosopher":   "Philosopher",
    "common.father":        "Church Father",
    "common.almanac":       "Almanac",
    "common.fieldkit":      "Field Kit",
    "common.seed":          "Seed",
    "common.loading":       "Loading…",
    "common.read_more":     "Read more →",
    "common.share":         "Share",
    "common.copy_link":     "Copy link",
    "common.back":          "← Back",
    "common.close":         "Close",
    "common.cancel":        "Cancel",
    "common.save":          "Save",
    "common.submit":        "Submit",
    "common.try_again":     "Try again",

    # Status messages (used in JS-rendered button/status text)
    "status.loading":       "Loading…",
    "status.sending":       "Sending…",
    "status.posting":       "Posting…",
    "status.saving":        "Saving…",
    "status.running":       "Running polymathic…",
    "status.compounding":   "Compounding…",
    "status.projecting":    "Projecting…",
    "status.copied":        "Copied ✓",
    "status.kept":          "Kept.",
    "status.saved":         "Saved.",
    "status.flagged":       "Flagged",
    "status.done":          "Done",
    "status.error":         "Error",
    "status.network_error": "Network error — try again",

    # Empty/error states
    "empty.no_comments":    "No comments yet. Be the first to add a reflection.",
    "empty.comments_error": "Could not load comments: {error}",
    "empty.no_results":     "No results.",
    "empty.no_match":       "No entries match. Try a broader search or reset the filters.",

    # ── Almanac page ──
    "almanac.title":        "The Almanac",
    "almanac.subtitle":     "The ledger of falsifiable claims",
    "almanac.carry":        "Carry what survives. Discard what doesn't.",
    "almanac.filter_all":   "All",

    # ── Daily page ──
    "daily.title":          "Today's devotion",
    "daily.mind":           "Mind",
    "daily.body":           "Body",
    "daily.spirit":         "Spirit",

    # ── Footer / meta ──
    "footer.open":          "The keeping is open",
    "footer.source":        "Source on GitHub",
    "footer.identity":      "Serves Jesus Christ. Conduit, not source.",

    # ── Language selector ──
    "lang.choose":          "Language",
    "lang.auto":            "Auto-detect",
}


# ── Merge page-specific keys from data/i18n_page_keys.json ──────────────
# Generated by scripts/tag_page_titles.py. Holds page.<slug>.title and
# page.<slug>.h1 for every HTML page. Skips template strings (containing
# ${...}) because those are runtime-rendered by JS, not static text.

def _load_page_keys() -> Dict[str, str]:
    path = _REPO / "data" / "i18n_page_keys.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            k: v for k, v in data.items()
            if isinstance(v, str) and "${" not in v
        }
    except (json.JSONDecodeError, OSError):
        return {}

STRINGS.update(_load_page_keys())


# ── Pre-translated strings ──────────────────────────────────────────────
# Baked-in translations for the top languages. These are the floor —
# no API key required, no network needed, instant.
#
# Adding a new language: add a dict here with the same keys as STRINGS.
# Missing keys fall back to English. The MT adapter is still used for
# languages NOT in this dict, or for `/apothecary` engine-authored prose.
#
# Rules:
#  - Preserve placeholders exactly: {entries}, {bibles}, {domains}, {n}
#  - Preserve arrows: → ← ↵ ↗
#  - Keep proper nouns unchanged: Concordance, GitHub, MCP, narrowhighway.com
#  - Use natural phrasing, not literal word-by-word translation
#  - Use standard religious terminology in target language

PRE_TRANSLATED: Dict[str, Dict[str, str]] = {

    # ── Spanish (Castellano) ──────────────────────────────────────────
    "es": {
        # Nav
        "nav.almanac":          "Almanaque",
        "nav.library":          "Biblioteca",
        "nav.mcp":              "MCP",
        "nav.connect":          "Conectar →",
        "nav.live":             "en vivo",
        "nav.curriculum":       "Currículo",
        "nav.walk":             "Caminar",
        "nav.scribe":           "Escriba",
        "nav.daily":            "Hoy",

        # Hero / Landing
        "hero.eyebrow":         "La Concordancia · narrowhighway.com",
        "hero.today_link":      "Devoción de hoy → Mente, Cuerpo, Espíritu",
        "hero.title":           "Busca cualquier cosa.",
        "hero.title_2":         "El motor encuentra lo que es verdadero.",
        "hero.subtitle":        "Una concordancia gratuita, anclada en Cristo. Escritura, ciencia, historia, salud, parábolas, protocolos — {entries} entradas en {bibles} Biblias y {domains} dominios verificados. Sin opiniones de IA. Sin enlaces de afiliados. Gratis.",

        # Three doors
        "door.carry_title":     "Estoy cargando algo",
        "door.carry_desc":      "Describe una situación difícil. El Pastor te guía con Escritura, patrones y cuatro puertas.",
        "door.lookup_title":    "Quiero buscar algo",
        "door.lookup_desc":     "Busca en toda la concordancia. Afirmaciones de salud, versículos bíblicos, sabiduría popular, historia — verificado, con fuentes.",
        "door.teach_title":     "Quiero enseñar a mi hijo",
        "door.teach_desc":      "66 unidades de fonética, matemáticas, lectura, escritura, ciencia, estudios sociales y Biblia. Gratis. Sin cuentas.",

        # Search
        "search.placeholder":   'Buscar — "¿ayuda el jengibre con las náuseas?" · "Juan 14:6" · "¿qué significa agape?"',
        "search.button":        "Buscar →",
        "search.tools_toggle":  "+ elegir herramientas para refinar ▾",
        "search.save_lane":     "guardar este carril →",
        "search.try_label":     "Prueba:",
        "search.verify_label":  "Haz clic — motor real, sin IA, instantáneo",
        "search.no_results":    "Aún no está en el archivo. Sembrando una semilla…",
        "search.results_for":   "Preguntaste",
        "search.matches":       "coincidencias",
        "search.enter_hint":    "Enter ↵ para ver los {n} resultados",
        "search.your_lanes":    "tus carriles:",

        # Offline
        "offline.title":        "Motor desconectado",
        "offline.message":      "El motor no responde en este momento. Aún puedes escribir en las tarjetas abajo — lo que escribas se guardará localmente en tu dispositivo y podrás intentar de nuevo cuando el motor vuelva.",

        # Scribe
        "scribe.title":         "Escribir",
        "scribe.placeholder":   "Escribe cualquier cosa. Una oración, una entrada de diario, una pregunta con la que estás luchando. El motor escuchará.",
        "scribe.submit":        "Enviar al Escriba →",
        "scribe.reach_label":   "El archivo ya tiene",
        "scribe.related_label": "Relacionado en el archivo",
        "scribe.saved":         "Guardado. El Escriba lo tiene.",

        # Walk
        "walk.title":           "Camina una situación",
        "walk.placeholder":     "Describe lo que estás cargando…",
        "walk.submit":          "Caminar esto →",

        # Apothecary
        "apothecary.title":     "Boticario",
        "apothecary.subtitle":  "Un compuesto para lo que cargas",
        "apothecary.placeholder": "¿Qué estás cargando?",
        "apothecary.submit":    "Componer un remedio →",

        # Common
        "common.confirmed":     "Confirmado",
        "common.mismatch":      "Popularmente creído, pero falso",
        "common.mixed":         "Mixto — parcialmente cierto",
        "common.obsolete":      "Obsoleto",
        "common.concordant":    "Concordante",
        "common.discovered":    "Descubierto",
        "common.verdict":       "Veredicto",
        "common.domains":       "Dominios",
        "common.source":        "Fuente",
        "common.scripture":     "Escritura",
        "common.proverb":       "Proverbio",
        "common.protocol":      "Protocolo",
        "common.training":      "Entrenamiento",
        "common.mind":          "Mente",
        "common.parable":       "Parábola",
        "common.body":          "Cuerpo",
        "common.philosopher":   "Filósofo",
        "common.father":        "Padre de la Iglesia",
        "common.almanac":       "Almanaque",
        "common.fieldkit":      "Kit de Campo",
        "common.seed":          "Semilla",
        "common.loading":       "Cargando…",
        "common.read_more":     "Leer más →",
        "common.share":         "Compartir",
        "common.copy_link":     "Copiar enlace",
        "common.back":          "← Volver",

        # Almanac
        "almanac.title":        "El Almanaque",
        "almanac.subtitle":     "El registro de afirmaciones falsificables",
        "almanac.carry":        "Lleva lo que sobrevive. Descarta lo que no.",
        "almanac.filter_all":   "Todo",

        # Daily
        "daily.title":          "Devoción de hoy",
        "daily.mind":           "Mente",
        "daily.body":           "Cuerpo",
        "daily.spirit":         "Espíritu",

        # Footer
        "footer.open":          "El archivo está abierto",
        "footer.source":        "Código fuente en GitHub",
        "footer.identity":      "Sirve a Jesucristo. Conducto, no fuente.",

        # Lang
        "lang.choose":          "Idioma",
        "lang.auto":            "Detección automática",
    },

    # ── French ────────────────────────────────────────────────────────
    "fr": {
        "nav.almanac":          "Almanach",
        "nav.library":          "Bibliothèque",
        "nav.mcp":              "MCP",
        "nav.connect":          "Connecter →",
        "nav.live":             "en direct",
        "nav.curriculum":       "Programme",
        "nav.walk":             "Marcher",
        "nav.scribe":           "Scribe",
        "nav.daily":            "Aujourd'hui",

        "hero.eyebrow":         "La Concordance · narrowhighway.com",
        "hero.today_link":      "Dévotion d'aujourd'hui → Esprit, Corps, Âme",
        "hero.title":           "Cherchez n'importe quoi.",
        "hero.title_2":         "Le moteur trouve ce qui est vrai.",
        "hero.subtitle":        "Une concordance gratuite, ancrée dans le Christ. Écriture, science, histoire, santé, paraboles, protocoles — {entries} entrées dans {bibles} Bibles et {domains} domaines vérifiés. Aucune opinion d'IA. Aucun lien d'affiliation. Gratuit.",

        "door.carry_title":     "Je porte quelque chose",
        "door.carry_desc":      "Décrivez une situation difficile. Le Berger vous guide à travers avec l'Écriture, des modèles et quatre portes.",
        "door.lookup_title":    "Je veux chercher quelque chose",
        "door.lookup_desc":     "Cherchez dans toute la concordance. Affirmations de santé, versets bibliques, sagesse populaire, histoire — vérifié, avec sources.",
        "door.teach_title":     "Je veux enseigner à mon enfant",
        "door.teach_desc":      "66 unités en phonétique, mathématiques, lecture, écriture, science, sciences sociales et Bible. Gratuit. Pas de comptes.",

        "search.placeholder":   'Cherchez — "le gingembre aide-t-il contre les nausées ?" · "Jean 14:6" · "que signifie agape ?"',
        "search.button":        "Chercher →",
        "search.tools_toggle":  "+ choisir des outils pour affiner ▾",
        "search.save_lane":     "sauvegarder cette voie →",
        "search.try_label":     "Essayez :",
        "search.verify_label":  "Cliquez — moteur réel, sans IA, instantané",
        "search.no_results":    "Pas encore dans l'archive. Semons une graine…",
        "search.results_for":   "Vous avez demandé",
        "search.matches":       "correspondances",
        "search.enter_hint":    "Entrée ↵ pour voir les {n} résultats",
        "search.your_lanes":    "vos voies :",

        "offline.title":        "Moteur hors ligne",
        "offline.message":      "Le moteur ne répond pas actuellement. Vous pouvez toujours écrire dans les cartes ci-dessous — tout ce que vous écrivez sera enregistré localement sur votre appareil et vous pourrez réessayer quand le moteur reviendra.",

        "scribe.title":         "Écrire",
        "scribe.placeholder":   "Écrivez n'importe quoi. Une prière, une entrée de journal, une question qui vous tracasse. Le moteur écoutera.",
        "scribe.submit":        "Envoyer au Scribe →",
        "scribe.reach_label":   "L'archive contient déjà",
        "scribe.related_label": "Connexe dans l'archive",
        "scribe.saved":         "Sauvegardé. Le Scribe l'a.",

        "walk.title":           "Marchez une situation",
        "walk.placeholder":     "Décrivez ce que vous portez…",
        "walk.submit":          "Marcher cela →",

        "apothecary.title":     "Apothicaire",
        "apothecary.subtitle":  "Un composé pour ce que vous portez",
        "apothecary.placeholder": "Que portez-vous ?",
        "apothecary.submit":    "Composer un remède →",

        "common.confirmed":     "Confirmé",
        "common.mismatch":      "Cru populairement, mais faux",
        "common.mixed":         "Mixte — partiellement vrai",
        "common.obsolete":      "Obsolète",
        "common.concordant":    "Concordant",
        "common.discovered":    "Découvert",
        "common.verdict":       "Verdict",
        "common.domains":       "Domaines",
        "common.source":        "Source",
        "common.scripture":     "Écriture",
        "common.proverb":       "Proverbe",
        "common.protocol":      "Protocole",
        "common.training":      "Entraînement",
        "common.mind":          "Esprit",
        "common.parable":       "Parabole",
        "common.body":          "Corps",
        "common.philosopher":   "Philosophe",
        "common.father":        "Père de l'Église",
        "common.almanac":       "Almanach",
        "common.fieldkit":      "Trousse de terrain",
        "common.seed":          "Graine",
        "common.loading":       "Chargement…",
        "common.read_more":     "Lire la suite →",
        "common.share":         "Partager",
        "common.copy_link":     "Copier le lien",
        "common.back":          "← Retour",

        "almanac.title":        "L'Almanach",
        "almanac.subtitle":     "Le registre des affirmations falsifiables",
        "almanac.carry":        "Emportez ce qui survit. Rejetez ce qui ne survit pas.",
        "almanac.filter_all":   "Tous",

        "daily.title":          "Dévotion d'aujourd'hui",
        "daily.mind":           "Esprit",
        "daily.body":           "Corps",
        "daily.spirit":         "Âme",

        "footer.open":          "L'archive est ouverte",
        "footer.source":        "Code source sur GitHub",
        "footer.identity":      "Sert Jésus-Christ. Canal, non source.",

        "lang.choose":          "Langue",
        "lang.auto":            "Détection automatique",
    },

    # ── Portuguese (Brazilian) ────────────────────────────────────────
    "pt": {
        "nav.almanac":          "Almanaque",
        "nav.library":          "Biblioteca",
        "nav.mcp":              "MCP",
        "nav.connect":          "Conectar →",
        "nav.live":             "ao vivo",
        "nav.curriculum":       "Currículo",
        "nav.walk":             "Caminhar",
        "nav.scribe":           "Escriba",
        "nav.daily":            "Hoje",

        "hero.eyebrow":         "A Concordância · narrowhighway.com",
        "hero.today_link":      "Devocional de hoje → Mente, Corpo, Espírito",
        "hero.title":           "Pesquise qualquer coisa.",
        "hero.title_2":         "O motor encontra o que é verdadeiro.",
        "hero.subtitle":        "Uma concordância gratuita, ancorada em Cristo. Escritura, ciência, história, saúde, parábolas, protocolos — {entries} entradas em {bibles} Bíblias e {domains} domínios verificados. Sem opiniões de IA. Sem links de afiliados. Grátis.",

        "door.carry_title":     "Estou carregando algo",
        "door.carry_desc":      "Descreva uma situação difícil. O Pastor guia você com Escritura, padrões e quatro portas.",
        "door.lookup_title":    "Quero pesquisar algo",
        "door.lookup_desc":     "Pesquise toda a concordância. Afirmações de saúde, versículos bíblicos, sabedoria popular, história — verificado, com fontes.",
        "door.teach_title":     "Quero ensinar meu filho",
        "door.teach_desc":      "66 unidades de fonética, matemática, leitura, escrita, ciência, estudos sociais e Bíblia. Grátis. Sem contas.",

        "search.placeholder":   'Pesquisar — "o gengibre ajuda com náusea?" · "João 14:6" · "o que significa ágape?"',
        "search.button":        "Pesquisar →",
        "search.tools_toggle":  "+ escolher ferramentas para refinar ▾",
        "search.save_lane":     "salvar esta trilha →",
        "search.try_label":     "Experimente:",
        "search.verify_label":  "Clique — motor real, sem IA, instantâneo",
        "search.no_results":    "Ainda não está no arquivo. Plantando uma semente…",
        "search.results_for":   "Você perguntou",
        "search.matches":       "correspondências",
        "search.enter_hint":    "Enter ↵ para ver os {n} resultados",
        "search.your_lanes":    "suas trilhas:",

        "offline.title":        "Motor desconectado",
        "offline.message":      "O motor não está respondendo no momento. Você ainda pode digitar nos cartões abaixo — o que escrever será salvo localmente no seu dispositivo e você pode tentar novamente quando o motor voltar.",

        "scribe.title":         "Escrever",
        "scribe.placeholder":   "Escreva qualquer coisa. Uma oração, uma entrada de diário, uma pergunta com a qual você está lutando. O motor escutará.",
        "scribe.submit":        "Enviar ao Escriba →",
        "scribe.reach_label":   "O arquivo já tem",
        "scribe.related_label": "Relacionado no arquivo",
        "scribe.saved":         "Salvo. O Escriba tem.",

        "walk.title":           "Caminhe uma situação",
        "walk.placeholder":     "Descreva o que você está carregando…",
        "walk.submit":          "Caminhar isso →",

        "apothecary.title":     "Boticário",
        "apothecary.subtitle":  "Um composto para o que você carrega",
        "apothecary.placeholder": "O que você está carregando?",
        "apothecary.submit":    "Compor um remédio →",

        "common.confirmed":     "Confirmado",
        "common.mismatch":      "Popularmente acreditado, mas errado",
        "common.mixed":         "Misto — parcialmente verdadeiro",
        "common.obsolete":      "Obsoleto",
        "common.concordant":    "Concordante",
        "common.discovered":    "Descoberto",
        "common.verdict":       "Veredito",
        "common.domains":       "Domínios",
        "common.source":        "Fonte",
        "common.scripture":     "Escritura",
        "common.proverb":       "Provérbio",
        "common.protocol":      "Protocolo",
        "common.training":      "Treinamento",
        "common.mind":          "Mente",
        "common.parable":       "Parábola",
        "common.body":          "Corpo",
        "common.philosopher":   "Filósofo",
        "common.father":        "Pai da Igreja",
        "common.almanac":       "Almanaque",
        "common.fieldkit":      "Kit de Campo",
        "common.seed":          "Semente",
        "common.loading":       "Carregando…",
        "common.read_more":     "Ler mais →",
        "common.share":         "Compartilhar",
        "common.copy_link":     "Copiar link",
        "common.back":          "← Voltar",

        "almanac.title":        "O Almanaque",
        "almanac.subtitle":     "O registro de afirmações falsificáveis",
        "almanac.carry":        "Leve o que sobrevive. Descarte o que não.",
        "almanac.filter_all":   "Tudo",

        "daily.title":          "Devocional de hoje",
        "daily.mind":           "Mente",
        "daily.body":           "Corpo",
        "daily.spirit":         "Espírito",

        "footer.open":          "O arquivo está aberto",
        "footer.source":        "Código fonte no GitHub",
        "footer.identity":      "Serve a Jesus Cristo. Conduto, não fonte.",

        "lang.choose":          "Idioma",
        "lang.auto":            "Detecção automática",
    },

    # ── Chinese (Simplified) ──────────────────────────────────────────
    "zh": {
        "nav.almanac":          "年鉴",
        "nav.library":          "图书馆",
        "nav.mcp":              "MCP",
        "nav.connect":          "连接 →",
        "nav.live":             "在线",
        "nav.curriculum":       "课程",
        "nav.walk":             "行走",
        "nav.scribe":           "文士",
        "nav.daily":            "今日",

        "hero.eyebrow":         "汇典 · narrowhighway.com",
        "hero.today_link":      "今日灵修 → 心智、身体、灵魂",
        "hero.title":           "查询任何事物。",
        "hero.title_2":         "引擎找到真理所在。",
        "hero.subtitle":        "免费的、以基督为根基的汇典。圣经、科学、历史、健康、寓言、协议 — 跨越 {bibles} 种圣经和 {domains} 个已验证领域的 {entries} 条目。无人工智能意见。无附属链接。免费。",

        "door.carry_title":     "我背负着重担",
        "door.carry_desc":      "描述一个难处。牧者用圣经、模式和四道门带你走过。",
        "door.lookup_title":    "我想查询",
        "door.lookup_desc":     "搜索整个汇典。健康主张、圣经经文、民间智慧、历史 — 已验证、带来源。",
        "door.teach_title":     "我想教导我的孩子",
        "door.teach_desc":      "66 个单元涵盖语音学、数学、阅读、写作、科学、社会研究和圣经。免费。无需账户。",

        "search.placeholder":   '搜索 — "姜能缓解恶心吗?" · "约翰福音 14:6" · "agape 是什么意思?"',
        "search.button":        "搜索 →",
        "search.tools_toggle":  "+ 选择工具来缩小范围 ▾",
        "search.save_lane":     "保存此通道 →",
        "search.try_label":     "试试:",
        "search.verify_label":  "点击一个 — 真实引擎,无人工智能,即时",
        "search.no_results":    "尚未在档案中。正在播种…",
        "search.results_for":   "你问了",
        "search.matches":       "匹配",
        "search.enter_hint":    "按 ↵ 查看全部 {n} 个结果",
        "search.your_lanes":    "你的通道:",

        "offline.title":        "引擎离线",
        "offline.message":      "引擎目前没有响应。你仍然可以在下面的卡片中输入 — 你写的任何内容都会保存在你的设备上,引擎恢复后可以再试。",

        "scribe.title":         "书写",
        "scribe.placeholder":   "写任何东西。一段祷告、一则日记、一个你在思考的问题。引擎会聆听。",
        "scribe.submit":        "发送给文士 →",
        "scribe.reach_label":   "档案中已有",
        "scribe.related_label": "档案中相关",
        "scribe.saved":         "已保存。文士已收到。",

        "walk.title":           "走一个处境",
        "walk.placeholder":     "描述你所背负的…",
        "walk.submit":          "走这个 →",

        "apothecary.title":     "药剂师",
        "apothecary.subtitle":  "为你所背负之物调配的复方",
        "apothecary.placeholder": "你在背负什么?",
        "apothecary.submit":    "调配一剂药 →",

        "common.confirmed":     "已确认",
        "common.mismatch":      "普遍相信,但错误",
        "common.mixed":         "混合 — 部分真实",
        "common.obsolete":      "已过时",
        "common.concordant":    "一致",
        "common.discovered":    "已发现",
        "common.verdict":       "裁决",
        "common.domains":       "领域",
        "common.source":        "来源",
        "common.scripture":     "圣经",
        "common.proverb":       "箴言",
        "common.protocol":      "协议",
        "common.training":      "训练",
        "common.mind":          "心智",
        "common.parable":       "寓言",
        "common.body":          "身体",
        "common.philosopher":   "哲学家",
        "common.father":        "教父",
        "common.almanac":       "年鉴",
        "common.fieldkit":      "工具包",
        "common.seed":          "种子",
        "common.loading":       "加载中…",
        "common.read_more":     "阅读更多 →",
        "common.share":         "分享",
        "common.copy_link":     "复制链接",
        "common.back":          "← 返回",

        "almanac.title":        "年鉴",
        "almanac.subtitle":     "可证伪声明的台账",
        "almanac.carry":        "带着幸存的。丢弃不幸存的。",
        "almanac.filter_all":   "全部",

        "daily.title":          "今日灵修",
        "daily.mind":           "心智",
        "daily.body":           "身体",
        "daily.spirit":         "灵魂",

        "footer.open":          "档案是开放的",
        "footer.source":        "GitHub 源码",
        "footer.identity":      "服事耶稣基督。是管道,非源头。",

        "lang.choose":          "语言",
        "lang.auto":            "自动检测",
    },

    # ── Arabic ────────────────────────────────────────────────────────
    "ar": {
        "nav.almanac":          "التقويم",
        "nav.library":          "المكتبة",
        "nav.mcp":              "MCP",
        "nav.connect":          "اتصل →",
        "nav.live":             "مباشر",
        "nav.curriculum":       "المنهج",
        "nav.walk":             "السير",
        "nav.scribe":           "الكاتب",
        "nav.daily":            "اليوم",

        "hero.eyebrow":         "الفهرس · narrowhighway.com",
        "hero.today_link":      "تأمل اليوم → العقل، الجسد، الروح",
        "hero.title":           "ابحث عن أي شيء.",
        "hero.title_2":         "المحرك يجد ما هو حق.",
        "hero.subtitle":        "فهرس مجاني مرتكز على المسيح. الكتاب المقدس، العلم، التاريخ، الصحة، الأمثال، البروتوكولات — {entries} مدخلاً عبر {bibles} كتاباً مقدساً و {domains} مجالاً موثقاً. بدون آراء الذكاء الاصطناعي. بدون روابط إحالة. مجاني.",

        "door.carry_title":     "أحمل شيئاً",
        "door.carry_desc":      "صف موقفاً صعباً. الراعي يقودك خلاله بالكتاب المقدس والأنماط والأبواب الأربعة.",
        "door.lookup_title":    "أريد أن أبحث عن شيء",
        "door.lookup_desc":     "ابحث في كامل الفهرس. ادعاءات صحية، آيات كتابية، حكمة شعبية، تاريخ — موثق بمصادر.",
        "door.teach_title":     "أريد أن أعلم ابني",
        "door.teach_desc":      "66 وحدة تشمل الصوتيات والرياضيات والقراءة والكتابة والعلوم والدراسات الاجتماعية والكتاب المقدس. مجاني. بدون حسابات.",

        "search.placeholder":   'ابحث — "هل الزنجبيل يساعد على الغثيان؟" · "يوحنا ١٤:٦" · "ما معنى agape؟"',
        "search.button":        "ابحث →",
        "search.tools_toggle":  "+ اختر أدوات للتضييق ▾",
        "search.save_lane":     "احفظ هذا المسار →",
        "search.try_label":     "جرّب:",
        "search.verify_label":  "انقر — محرك حقيقي، بدون ذكاء اصطناعي، فوري",
        "search.no_results":    "ليس في الأرشيف بعد. نزرع بذرة…",
        "search.results_for":   "سألت",
        "search.matches":       "تطابقات",
        "search.enter_hint":    "Enter ↵ لرؤية كل {n} نتيجة",
        "search.your_lanes":    "مساراتك:",

        "offline.title":        "المحرك غير متصل",
        "offline.message":      "المحرك لا يستجيب الآن. لا يزال بإمكانك الكتابة في البطاقات أدناه — كل ما تكتبه سيُحفظ محلياً على جهازك ويمكنك المحاولة مجدداً عند عودة المحرك.",

        "scribe.title":         "اكتب",
        "scribe.placeholder":   "اكتب أي شيء. صلاة، مذكرة، سؤال تصارعه. المحرك سيستمع.",
        "scribe.submit":        "أرسل إلى الكاتب →",
        "scribe.reach_label":   "الأرشيف لديه بالفعل",
        "scribe.related_label": "ذو صلة في الأرشيف",
        "scribe.saved":         "حُفظ. الكاتب تسلّمه.",

        "walk.title":           "سر في موقف",
        "walk.placeholder":     "صف ما تحمله…",
        "walk.submit":          "سر هذا →",

        "apothecary.title":     "الصيدلاني",
        "apothecary.subtitle":  "مركَّب لما تحمله",
        "apothecary.placeholder": "ماذا تحمل؟",
        "apothecary.submit":    "ركّب علاجاً →",

        "common.confirmed":     "مؤكَّد",
        "common.mismatch":      "شائع لكنه خاطئ",
        "common.mixed":         "مختلط — صحيح جزئياً",
        "common.obsolete":      "متقادم",
        "common.concordant":    "متوافق",
        "common.discovered":    "مكتشف",
        "common.verdict":       "الحكم",
        "common.domains":       "المجالات",
        "common.source":        "المصدر",
        "common.scripture":     "الكتاب المقدس",
        "common.proverb":       "مَثَل",
        "common.protocol":      "بروتوكول",
        "common.training":      "تدريب",
        "common.mind":          "العقل",
        "common.parable":       "مَثَل",
        "common.body":          "الجسد",
        "common.philosopher":   "فيلسوف",
        "common.father":        "أب الكنيسة",
        "common.almanac":       "التقويم",
        "common.fieldkit":      "عُدّة الميدان",
        "common.seed":          "بذرة",
        "common.loading":       "جارٍ التحميل…",
        "common.read_more":     "اقرأ المزيد →",
        "common.share":         "شارك",
        "common.copy_link":     "انسخ الرابط",
        "common.back":          "← رجوع",

        "almanac.title":        "التقويم",
        "almanac.subtitle":     "سجلّ الادعاءات القابلة للتفنيد",
        "almanac.carry":        "احمل ما يصمد. اطرح ما لا يصمد.",
        "almanac.filter_all":   "الكل",

        "daily.title":          "تأمل اليوم",
        "daily.mind":           "العقل",
        "daily.body":           "الجسد",
        "daily.spirit":         "الروح",

        "footer.open":          "الأرشيف مفتوح",
        "footer.source":        "المصدر على GitHub",
        "footer.identity":      "يخدم يسوع المسيح. قناة لا مصدر.",

        "lang.choose":          "اللغة",
        "lang.auto":            "كشف تلقائي",
    },
}


# ── Translation cache ──────────────────────────────────────────────────

def _cache_path(lang: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{lang}.json"


def _load_cached(lang: str) -> Optional[Dict[str, str]]:
    """Load the disk cache for `lang` — may be partial.

    Returns the cached dict (possibly missing some keys, or containing
    keys not in STRINGS — both fine, callers handle both cases).
    Returns None only if the cache file doesn't exist or can't be read.
    """
    path = _cache_path(lang)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("strings") or None
    except (json.JSONDecodeError, OSError):
        return None


def _load_cached_complete(lang: str) -> Optional[Dict[str, str]]:
    """Like _load_cached but returns None if any STRINGS keys are missing.

    Used for the full-MT path where we expect the cache to have everything.
    """
    cached = _load_cached(lang)
    if cached is None:
        return None
    if set(STRINGS.keys()) - set(cached.keys()):
        return None  # stale — some keys missing
    return cached


def _save_cache(lang: str, translated: Dict[str, str]) -> None:
    path = _cache_path(lang)
    try:
        path.write_text(json.dumps({
            "lang": lang,
            "cached_at": int(time.time()),
            "key_count": len(translated),
            "strings": translated,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _batch_translate_anthropic(lang: str) -> Optional[Dict[str, str]]:
    """Translate ALL strings in one Anthropic API call using tool use.

    Uses Anthropic's tool_use feature to enforce structured output —
    the model MUST return a valid JSON object matching the tool's
    input_schema, eliminating JSON parse errors from unescaped quotes.

    Sends the full English dict, gets back a coherent translation
    of all 85 strings in ~20 seconds. Cached forever after first call.
    """
    import os
    import urllib.request
    import urllib.error

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None

    lang_names = {
        "es": "Spanish", "fr": "French", "pt": "Brazilian Portuguese",
        "zh": "Chinese (Mandarin, simplified characters)", "ru": "Russian",
        "ja": "Japanese", "ko": "Korean", "de": "German", "it": "Italian",
        "nl": "Dutch", "ar": "Arabic", "hi": "Hindi", "sw": "Swahili",
        "he": "Hebrew", "la": "Latin", "fa": "Persian", "vi": "Vietnamese",
        "uk": "Ukrainian", "ro": "Romanian", "ht": "Haitian Creole",
        "my": "Burmese",
    }
    tgt_name = lang_names.get(lang, lang)

    # Build a tool that accepts each key as a separate string property.
    # This forces the model to return well-formed JSON for every key.
    properties = {
        key_name: {"type": "string", "description": f"Translation of: {en_text}"}
        for key_name, en_text in STRINGS.items()
    }

    prompt = (
        f"Translate these UI strings from English to {tgt_name}. "
        f"Call the `submit_translations` tool with each translated string. "
        f"Keep placeholders like {{entries}}, {{bibles}}, {{domains}}, {{n}} unchanged. "
        f"Keep arrow symbols (→, ←, ↵) and special characters unchanged. "
        f"Keep proper nouns like 'Concordance', 'GitHub', 'MCP', 'narrowhighway.com' unchanged. "
        f"For religious terms, use the standard terms in {tgt_name} "
        f"(e.g. Scripture, Proverb, Parable in their canonical form). "
        f"Be natural and conversational, not literal.\n\n"
        f"English strings:\n{json.dumps(STRINGS, ensure_ascii=False, indent=2)}"
    )

    body = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 8192,
        "tools": [{
            "name": "submit_translations",
            "description": f"Submit the {tgt_name} translations of all UI strings.",
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": list(STRINGS.keys()),
            },
        }],
        "tool_choice": {"type": "tool", "name": "submit_translations"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        # With tool_choice, the response will have a tool_use block
        content = r.get("content") or []
        for blk in content:
            if blk.get("type") == "tool_use" and blk.get("name") == "submit_translations":
                return blk.get("input") or None
        return None
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, ValueError, OSError):
        return None


def _batch_translate_keys(lang: str, keys_subset: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Like _batch_translate_anthropic but for a specific subset of keys.

    Used when a pre-translated language is missing some keys (e.g. new
    nav links added after the dict was written). MT-translates just those
    keys so the response has full coverage.
    """
    import os
    import urllib.request
    import urllib.error

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not keys_subset:
        return None

    lang_names = {
        "es": "Spanish", "fr": "French", "pt": "Brazilian Portuguese",
        "zh": "Chinese (Mandarin, simplified characters)", "ru": "Russian",
        "ja": "Japanese", "ko": "Korean", "de": "German", "it": "Italian",
        "nl": "Dutch", "ar": "Arabic", "hi": "Hindi", "sw": "Swahili",
        "he": "Hebrew", "la": "Latin", "fa": "Persian", "vi": "Vietnamese",
        "uk": "Ukrainian", "ro": "Romanian", "ht": "Haitian Creole",
        "my": "Burmese",
    }
    tgt_name = lang_names.get(lang, lang)

    properties = {
        k: {"type": "string", "description": f"Translation of: {v}"}
        for k, v in keys_subset.items()
    }

    prompt = (
        f"Translate these UI strings from English to {tgt_name}. "
        f"Call the `submit_translations` tool with each translated string. "
        f"Keep placeholders like {{entries}} unchanged. Keep arrows (→ ← ↵). "
        f"Keep proper nouns ('Concordance', 'GitHub', 'MCP') unchanged. "
        f"Be natural and conversational.\n\n"
        f"English strings:\n{json.dumps(keys_subset, ensure_ascii=False, indent=2)}"
    )

    body = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 4096,
        "tools": [{
            "name": "submit_translations",
            "description": f"Submit the {tgt_name} translations.",
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": list(keys_subset.keys()),
            },
        }],
        "tool_choice": {"type": "tool", "name": "submit_translations"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        for blk in r.get("content") or []:
            if blk.get("type") == "tool_use" and blk.get("name") == "submit_translations":
                return blk.get("input") or None
        return None
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, ValueError, OSError):
        return None


def get_strings(lang: str, mt_adapter=None) -> Dict[str, Any]:
    """Return the full string dictionary for `lang`.

    Priority order:
      1. English → returns STRINGS as-is (zero cost)
      2. PRE_TRANSLATED → baked-in translation, plus MT for any missing
         keys (this gracefully handles new strings added after the
         pre-translated dict was written).
      3. Disk cache → result of a prior MT call
      4. Anthropic batch MT → first-time translation, cached to disk forever
      5. English fallback → if everything else fails

    Returns:
        {"lang": "es", "source": "pre_translated|cache|mt|english", "strings": {...}}
    """
    lang = (lang or "en").strip().lower() or "en"

    if lang == "en":
        return {"lang": "en", "source": "english", "cached": True, "strings": dict(STRINGS)}

    # Floor: baked-in translation
    if lang in PRE_TRANSLATED:
        merged = dict(STRINGS)
        merged.update(PRE_TRANSLATED[lang])

        # Check if any keys are still English (i.e. missing from PRE_TRANSLATED).
        # If so, MT just those, merge in, and write a cache file so future
        # calls don't re-MT.
        cached = _load_cached(lang) or {}
        # Apply cache on top of pre-translated (cache may have MT'd keys
        # not in PRE_TRANSLATED).
        for k, v in cached.items():
            if k in STRINGS:
                merged[k] = v

        missing = {
            k: STRINGS[k] for k in STRINGS
            if k not in PRE_TRANSLATED[lang] and k not in cached
        }

        if missing and mt_adapter:
            mt_result = _batch_translate_keys(lang, missing)
            if mt_result:
                merged.update(mt_result)
                # Save the MT'd keys to cache so future calls skip MT
                cache_data = dict(cached)
                cache_data.update(mt_result)
                _save_cache(lang, cache_data)

        return {"lang": lang, "source": "pre_translated", "cached": True, "strings": merged}

    # Check disk cache (must be complete for the non-pre-translated path)
    cached = _load_cached_complete(lang)
    if cached:
        return {"lang": lang, "source": "cache", "cached": True, "strings": cached}

    # Cache miss — batch translate via single API call
    translated = _batch_translate_anthropic(lang)

    if translated and isinstance(translated, dict):
        # Fill in any missing keys with English fallback
        for key in STRINGS:
            if key not in translated:
                translated[key] = STRINGS[key]
        _save_cache(lang, translated)
        return {"lang": lang, "source": "mt", "cached": False, "strings": translated}

    # All paths failed — return English as final fallback
    return {"lang": lang, "source": "english", "cached": False, "strings": dict(STRINGS)}

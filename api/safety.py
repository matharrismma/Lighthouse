"""Crisis safety net — the floor under the floor.

Some conditions a person brings are acute: thoughts of suicide or self-harm, an
overdose, being in danger right now. On those, the most loving and honest thing
the engine can do is get out of the way and point to a real person who can help
immediately. The wisdom in the substrate is real, but it is not triage, and a
remedy must never stand between someone in danger and the help that can keep
them safe.

Deterministic by design. Detection is phrase-based (no oracle): a safety net has
to fire reliably and instantly, not depend on a model call that could be slow,
budgeted-out, or wrong. It is precise, not broad — it triggers on acute,
self-directed signals only, so the message keeps its weight. A crisis banner on
every "I feel stressed" would desensitize and erode trust; the goal is that when
it does appear, it is believed.

When it fires, it points three ways, in order:
  1. to immediate crisis help (988 / 911 / a text line / a worldwide directory),
  2. to a real person the visitor already trusts,
  3. and — because a person's worth never hinged on this tool — to Christ,
     briefly, gently, never preachy, never as a substitute for the call.

Success is the person reaching real help and needing this tool less.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Acute, self-directed signals. Word-boundaried and phrase-shaped so we don't
# fire on "I could kill HIM" (anger at another), "dying to see you" (idiom), or
# "dead tired". Erring toward care on a clear self-directed phrase is acceptable:
# a gentle "if you're struggling, help is here" never harms, and a miss can.
_CRISIS_PATTERNS = [
    r"\bkill(?:ing)?\s+my\s?self\b",
    r"\bend(?:ing)?\s+(?:my\s+life|my\s+own\s+life|it\s+all)\b",
    r"\btake\s+my\s+(?:own\s+)?life\b",
    r"\bwan(?:t|na)\s+to?\s*die\b",
    r"\bwant\s+to\s+die\b",
    r"\bwish\s+i\s+(?:was|were)\s+dead\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:living|live|life|go\s+on)\b",
    r"\bnot\s+worth\s+living\b",
    r"\bdon'?t\s+want\s+to\s+(?:be\s+here|live|exist|wake\s+up)\b",
    r"\bsuicid",            # suicide, suicidal
    r"\bhurt(?:ing)?\s+my\s?self\b",
    r"\bcut(?:ting)?\s+my\s?self\b",
    r"\bself[-\s]?harm",
    r"\boverdos",           # overdose, overdosed, overdosing
    r"\bkill\s+my\s?self\b",
]

# Non-English acute signals. Detection runs language-AGNOSTIC: every pattern is
# matched against the text regardless of the declared UI language, so a Spanish
# "quiero morir" typed into an English page still fires. These are distinctive
# crisis phrases, so cross-language false positives are negligible. High-
# confidence phrases only (same precision discipline as the English set).
_CRISIS_PATTERNS_INTL = [
    # Spanish
    r"quiero\s+morir", r"me\s+quiero\s+matar", r"quiero\s+matarme", r"\bmatarme\b",
    r"no\s+quiero\s+vivir", r"mejor\s+muerto", r"hacerme\s+da[ñn]o",
    # French
    r"je\s+veux\s+mourir", r"envie\s+de\s+mourir", r"\bme\s+tuer\b", r"me\s+suicider",
    r"plus\s+envie\s+de\s+vivre", r"me\s+faire\s+du\s+mal",
    # Portuguese
    r"quero\s+morrer", r"\bme\s+matar\b", r"matar[\s-]?me", r"n[ãa]o\s+quero\s+viver",
    # Italian
    r"voglio\s+morire", r"uccidermi", r"ammazzarmi", r"non\s+voglio\s+vivere",
    r"farmi\s+del\s+male",
    # German
    r"ich\s+will\s+sterben", r"nicht\s+mehr\s+leben", r"mich\s+umbringen",
    r"bringe?\s+mich\s+um", r"selbstmord",
    # accented / cross-Romance suicide stem (suicídio, suicidarsi, suicidarme…)
    r"suic[ií]d",
    # Chinese (high-confidence)
    r"自杀", r"想死", r"不想活",
    # Arabic (high-confidence)
    r"انتحار", r"أريد\s+أن\s+أموت", r"اريد\s+ان\s+اموت", r"اقتل\s+نفسي",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS + _CRISIS_PATTERNS_INTL), re.IGNORECASE)


def crisis_check(text: str, lang: str = "en") -> Optional[Dict[str, Any]]:
    """Return a structured safety block if `text` carries an acute-risk signal,
    else None. Detection is language-agnostic; the BLOCK is localized to `lang`
    where we have a confident translation (else English with the worldwide
    helpline leading). Deterministic; safe to call on every input."""
    if not text or not _CRISIS_RE.search(text):
        return None
    return safety_block(lang)


# The English immediate-help list (988 leads — this default is for US English).
_EN_IMMEDIATE: List[Dict[str, str]] = [
    {"name": "988 Suicide & Crisis Lifeline (US)", "action": "Call or text 988",
     "detail": "Free, confidential, 24/7. You can also chat at 988lifeline.org."},
    {"name": "Emergency services", "action": "Call 911 (US) or your local emergency number",
     "detail": "If you are in immediate danger or might act on these thoughts."},
    {"name": "Crisis Text Line", "action": "Text HOME to 741741 (US / Canada / UK)",
     "detail": "Text back and forth with a trained crisis counselor."},
    {"name": "Find a helpline (worldwide)", "action": "findahelpline.com",
     "detail": "Free, confidential crisis lines listed by country."},
]

# For non-English speakers we LEAD with the worldwide directory (findahelpline.com
# routes by country) — it is the safe universal — then the local emergency number,
# then 988 clearly marked US. `detail` text is localized per language.
_INTL_HELP_DETAIL = {
    "es": ("Líneas de crisis gratuitas y confidenciales, por país.",
           "Si estás en peligro inmediato.",
           "Línea de crisis de EE. UU. (en inglés/español)."),
    "fr": ("Lignes d'écoute gratuites et confidentielles, par pays.",
           "Si vous êtes en danger immédiat.",
           "Ligne de crise des États-Unis (en anglais)."),
    "pt": ("Linhas de crise gratuitas e confidenciais, por país.",
           "Se você estiver em perigo imediato.",
           "Linha de crise dos EUA (em inglês/espanhol)."),
    "de": ("Kostenlose, vertrauliche Krisen-Hotlines, nach Land.",
           "Wenn Sie in unmittelbarer Gefahr sind.",
           "US-Krisenhotline (auf Englisch)."),
    "it": ("Linee di crisi gratuite e riservate, per Paese.",
           "Se sei in pericolo immediato.",
           "Linea di crisi degli USA (in inglese)."),
}
_INTL_HELP_DETAIL_EN = ("Free, confidential crisis lines listed by country.",
                        "If you are in immediate danger.",
                        "US crisis line (English).")

# Localized block text. English is the canonical/default and is kept byte-for-byte.
# es/fr/pt/de/it are hand-authored (public-domain Psalm 34:18 in each language).
# Any other language falls back to English text but still leads with the worldwide
# helpline — better an honest, clear English block + a country directory than a
# shaky machine translation of life-safety wording.
_BLOCK_TEXT = {
    "en": {
        "headline": "Please reach a real person right now — you deserve immediate help, "
                    "and this tool cannot give it.",
        "a_real_person": "Tell someone you trust what you just told me — a friend, a "
                         "family member, a pastor. You do not have to carry this alone, "
                         "and saying it out loud to a person is itself a step toward safety.",
        "in_christ": "You are not beyond help and you are not a burden. Your life has "
                     "worth that does not depend on how you feel right now, or on anything "
                     "this tool can offer. “The LORD is near to the brokenhearted and "
                     "saves the crushed in spirit.” (Psalm 34:18)",
        "honest_limit": "This is a tool, not a counselor or a doctor. It cannot keep you "
                        "safe — a real person can. Please reach out above before reading "
                        "anything else here.",
    },
    "es": {
        "headline": "Por favor, busca a una persona real ahora mismo — mereces ayuda "
                    "inmediata, y esta herramienta no puede dártela.",
        "a_real_person": "Cuéntale a alguien de confianza lo que acabas de decirme — un "
                         "amigo, un familiar, un pastor. No tienes que llevar esto solo/a; "
                         "decirlo en voz alta a una persona ya es un paso hacia la seguridad.",
        "in_christ": "No estás más allá de toda ayuda y no eres una carga. Tu vida tiene "
                     "un valor que no depende de cómo te sientes ahora, ni de nada que esta "
                     "herramienta pueda ofrecer. «Cercano está Jehová a los quebrantados de "
                     "corazón; y salva a los contritos de espíritu.» (Salmo 34:18)",
        "honest_limit": "Esto es una herramienta, no un consejero ni un médico. No puede "
                        "mantenerte a salvo — una persona real sí. Por favor, comunícate con "
                        "alguien de arriba antes de leer cualquier otra cosa.",
    },
    "fr": {
        "headline": "S'il vous plaît, contactez une personne réelle maintenant — vous "
                    "méritez une aide immédiate, et cet outil ne peut pas vous la donner.",
        "a_real_person": "Dites à quelqu'un en qui vous avez confiance ce que vous venez de "
                         "me dire — un ami, un proche, un pasteur. Vous n'avez pas à porter "
                         "cela seul(e) ; le dire à voix haute à une personne est déjà un pas "
                         "vers la sécurité.",
        "in_christ": "Vous n'êtes pas au-delà de tout secours et vous n'êtes pas un fardeau. "
                     "Votre vie a une valeur qui ne dépend pas de ce que vous ressentez en ce "
                     "moment, ni de rien que cet outil puisse offrir. « L'Éternel est près de "
                     "ceux qui ont le cœur brisé, il sauve ceux qui ont l'esprit abattu. » "
                     "(Psaume 34:18)",
        "honest_limit": "Ceci est un outil, pas un conseiller ni un médecin. Il ne peut pas "
                        "vous protéger — une personne réelle le peut. Veuillez contacter "
                        "quelqu'un ci-dessus avant de lire autre chose.",
    },
    "pt": {
        "headline": "Por favor, procure uma pessoa real agora mesmo — você merece ajuda "
                    "imediata, e esta ferramenta não pode oferecê-la.",
        "a_real_person": "Conte a alguém de confiança o que você acabou de me dizer — um "
                         "amigo, um familiar, um pastor. Você não precisa carregar isso "
                         "sozinho(a); dizer em voz alta a uma pessoa já é um passo rumo à "
                         "segurança.",
        "in_christ": "Você não está além de toda ajuda e não é um fardo. Sua vida tem um "
                     "valor que não depende de como você se sente agora, nem de nada que esta "
                     "ferramenta possa oferecer. «Perto está o SENHOR dos que têm o coração "
                     "quebrantado, e salva os contritos de espírito.» (Salmos 34:18)",
        "honest_limit": "Isto é uma ferramenta, não um conselheiro nem um médico. Ela não "
                        "pode manter você em segurança — uma pessoa real pode. Por favor, "
                        "fale com alguém acima antes de ler qualquer outra coisa.",
    },
    "de": {
        "headline": "Bitte wenden Sie sich jetzt sofort an einen echten Menschen — Sie "
                    "verdienen sofortige Hilfe, und dieses Werkzeug kann sie nicht geben.",
        "a_real_person": "Sagen Sie einer Person, der Sie vertrauen, was Sie mir gerade "
                         "gesagt haben — einem Freund, einem Angehörigen, einem Seelsorger. "
                         "Sie müssen das nicht allein tragen; es einer Person laut zu sagen "
                         "ist schon ein Schritt zur Sicherheit.",
        "in_christ": "Sie sind nicht verloren und Sie sind keine Last. Ihr Leben hat einen "
                     "Wert, der nicht davon abhängt, wie Sie sich gerade fühlen, oder von "
                     "irgendetwas, das dieses Werkzeug bieten kann. „Der HERR ist nahe denen, "
                     "die zerbrochenen Herzens sind, und hilft denen, die ein zerschlagenes "
                     "Gemüt haben.“ (Psalm 34:18)",
        "honest_limit": "Dies ist ein Werkzeug, kein Berater und kein Arzt. Es kann Sie "
                        "nicht schützen — ein echter Mensch kann es. Bitte wenden Sie sich an "
                        "jemanden oben, bevor Sie etwas anderes lesen.",
    },
    "it": {
        "headline": "Per favore, contatta subito una persona reale — meriti aiuto "
                    "immediato, e questo strumento non può dartelo.",
        "a_real_person": "Di' a qualcuno di cui ti fidi ciò che mi hai appena detto — un "
                         "amico, un familiare, un pastore. Non devi portare questo peso da "
                         "solo/a; dirlo ad alta voce a una persona è già un passo verso la "
                         "sicurezza.",
        "in_christ": "Non sei oltre ogni aiuto e non sei un peso. La tua vita ha un valore "
                     "che non dipende da come ti senti ora, né da nulla che questo strumento "
                     "possa offrire. «Il SIGNORE è vicino a quelli che hanno il cuore rotto, "
                     "e salva quelli che hanno lo spirito affranto.» (Salmo 34:18)",
        "honest_limit": "Questo è uno strumento, non un consulente né un medico. Non può "
                        "tenerti al sicuro — una persona reale sì. Per favore, contatta "
                        "qualcuno qui sopra prima di leggere qualsiasi altra cosa.",
    },
}


def _intl_immediate(lang: str) -> List[Dict[str, str]]:
    d = _INTL_HELP_DETAIL.get(lang, _INTL_HELP_DETAIL_EN)
    return [
        {"name": "Find a helpline (worldwide) · findahelpline.com",
         "action": "findahelpline.com", "detail": d[0]},
        {"name": "Emergency services", "action": "Your local emergency number", "detail": d[1]},
        {"name": "988 Suicide & Crisis Lifeline (US)", "action": "Call or text 988", "detail": d[2]},
    ]


def safety_block(lang: str = "en") -> Dict[str, Any]:
    """The crisis response. Stable shape so any surface (apothecary, Shepherd,
    a generative reply) renders it first and identically. `lang` localizes the
    wording and, for non-English, leads with the worldwide helpline directory."""
    lang = (lang or "en").strip().lower()[:5]
    if lang.startswith("en") or "-" in lang and lang.split("-")[0] == "en":
        lang = "en"
    else:
        lang = lang.split("-")[0]
    text = _BLOCK_TEXT.get(lang, _BLOCK_TEXT["en"])
    immediate = _EN_IMMEDIATE if lang == "en" else _intl_immediate(lang)
    return {
        "triggered": True,
        "severity": "crisis",
        "lang": lang if lang in _BLOCK_TEXT else "en",
        "headline": text["headline"],
        "immediate": immediate,
        "a_real_person": text["a_real_person"],
        "in_christ": text["in_christ"],
        "honest_limit": text["honest_limit"],
    }

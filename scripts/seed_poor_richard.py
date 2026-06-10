#!/usr/bin/env python
"""Seed 25 Poor Richard's Almanack aphorisms into the almanac.

Poor Richard's (1732–1758, Benjamin Franklin) is solidly PD by age. Each
entry below carries the verbatim Franklin text (or its commonly-cited form)
+ a verifier-anchored verdict + Shepherd-voice wisdom.

Several entries land MIXED rather than CONFIRMED because the aphorism
contains a truth at the kernel but overstates the rule. The engine is
honest about that — keeping what survives, qualifying what doesn't.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    {
        "id": "saying_franklin_early_to_bed",
        "kind": "saying",
        "title": "Early to bed and early to rise, makes a man healthy, wealthy, and wise",
        "saying": "Early to bed and early to rise, makes a man healthy, wealthy, and wise.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1735, "author": "Benjamin Franklin"},
        "category": "health",
        "domains": ["exercise_science", "medicine", "finance"],
        "axes": ["metabolism", "time_sequence", "phase"],
        "verdict": "MIXED",
        "verification": "Health: yes — chronic sleep curtailment and circadian misalignment predict cardiovascular, metabolic, and cognitive harm (UK Biobank cohorts, ~500k subjects). Wealth: weak — the rich-and-early-rising association is selection, not cause; night-shift work disproportionately falls on the poor. Wise: depends on what wisdom is. The aphorism is true about the body, oversold about the bank account, and uncomputable about the soul.",
        "wisdom": "The body keeps a clock; honoring it pays dividends in years. The market doesn't care what time you got up. The Shepherd carries the first claim with confidence, qualifies the second, and treats the third as your business with God.",
        "triggers": {"keywords": ["early to bed", "sleep", "circadian", "Franklin", "Poor Richard's"], "axes": ["metabolism", "time_sequence"]},
    },
    {
        "id": "saying_franklin_penny_saved",
        "kind": "saying",
        "title": "A penny saved is two pence clear",
        "saying": "A penny saved is two pence clear. (Modernised: a penny saved is a penny earned.)",
        "source": {"publication": "Poor Richard's Almanack", "year": 1737, "author": "Benjamin Franklin"},
        "category": "finance",
        "domains": ["finance", "economics", "mathematics"],
        "axes": ["conservation_balance", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Franklin's original 'two pence clear' is the sharper claim: a saved penny is worth more than an earned one, because earned pennies face tax. Modern equivalent: a $1 reduction in spending is worth ~$1.30 of pre-tax income at a 23% marginal rate. The arithmetic holds.",
        "wisdom": "Savings compound; income is taxed. A reduction in expenditure has the strongest possible ROI: zero risk, immediate, fully kept. The Shepherd brings this when the user is chasing income while leaks drain it.",
        "triggers": {"keywords": ["penny saved", "savings", "frugality", "Franklin", "compound interest"], "axes": ["conservation_balance"]},
    },
    {
        "id": "saying_franklin_lost_time",
        "kind": "saying",
        "title": "Lost time is never found again",
        "saying": "Lost time is never found again.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1747, "author": "Benjamin Franklin"},
        "category": "reasoning",
        "domains": ["phase", "operations_research"],
        "axes": ["time_sequence", "conservation_balance"],
        "verdict": "CONFIRMED",
        "verification": "Time is the one resource with no inverse operation. Money lost can be earned back; relationships broken can mend; tools lost can be replaced. The arrow of time is fundamentally asymmetric (thermodynamics: ΔS ≥ 0). Lost time is, in the strict physical sense, never recovered.",
        "wisdom": "Of every resource the engine tracks — money, materials, energy, attention — time is the only one with a verdict already written. The Shepherd brings this when the user is debating whether to start.",
        "triggers": {"keywords": ["lost time", "time management", "procrastination", "Franklin", "arrow of time"], "axes": ["time_sequence"]},
    },
    {
        "id": "saying_franklin_diligence",
        "kind": "saying",
        "title": "Diligence is the mother of good luck",
        "saying": "Diligence is the mother of good luck.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1736, "author": "Benjamin Franklin"},
        "category": "reasoning",
        "domains": ["statistics", "operations_research"],
        "axes": ["time_sequence", "reasoning"],
        "verdict": "CONFIRMED",
        "verification": "Probability of at least one success in N attempts at independent probability p is 1 − (1−p)^N. For p=0.05, the chance of zero successes in 50 tries is 7.7%; in 100 tries, 0.6%. Sustained attempts convert low-probability events into near-certainties. The 'luck' is the back end of a long tail of attempts.",
        "wisdom": "Repeated low-probability tries become high-probability outcomes. The Shepherd brings this when the user feels unlucky after one or two attempts at something that needed twenty.",
        "triggers": {"keywords": ["diligence", "luck", "persistence", "Franklin", "Bernoulli trials"], "axes": ["time_sequence", "reasoning"]},
    },
    {
        "id": "saying_franklin_haste_waste",
        "kind": "saying",
        "title": "Haste makes waste",
        "saying": "Haste makes waste.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1753, "author": "Benjamin Franklin"},
        "category": "reasoning",
        "domains": ["operations_research", "manufacturing"],
        "axes": ["time_sequence", "conservation_balance"],
        "verdict": "MIXED",
        "verification": "Often true in manufacturing (defect rate rises with throughput pressure past optimum) and surgery (rushed procedures correlate with complications). Often false in trading or in emergencies (delay costs more than risk). The aphorism is a rule with exceptions, not a law. The Shepherd reads it as: speed without method is waste; speed with method is throughput.",
        "wisdom": "Haste fails when the cost of error exceeds the cost of delay. In construction, surgery, and code: slow is fast. In firefighting, triage, and falling markets: fast is slow. Know which regime you're in.",
        "triggers": {"keywords": ["haste makes waste", "slow is fast", "Franklin", "throughput"], "axes": ["time_sequence", "conservation_balance"]},
    },
    {
        "id": "saying_franklin_three_secret",
        "kind": "saying",
        "title": "Three may keep a secret, if two of them are dead",
        "saying": "Three may keep a secret, if two of them are dead.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1735, "author": "Benjamin Franklin"},
        "category": "cybersecurity",
        "domains": ["information_theory", "cryptography", "statistics"],
        "axes": ["information_encoding", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Secret-keeping channel capacity decays super-linearly with the number of holders. If P(any one leaks per year) = p, then P(secret survives N people, T years) = (1−p)^(N·T). For p=0.05, N=3, T=10: survival = 22%. For N=10, T=10: survival = 0.6%. The aphorism's punchline (dead people don't leak) is the only honest preservation.",
        "wisdom": "Operational secrecy decays with people × time. The Shepherd brings this when the user underestimates how fragile a 'known by a few' secret is — and when a published Kerckhoffs-principle approach (security through key, not obscurity) would serve them better.",
        "triggers": {"keywords": ["three keep a secret", "secrecy", "operational security", "Franklin", "leak probability"], "axes": ["information_encoding", "authority_trust"]},
    },
    {
        "id": "saying_franklin_small_leak",
        "kind": "saying",
        "title": "Beware of little expenses; a small leak will sink a great ship",
        "saying": "Beware of little expenses; a small leak will sink a great ship.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1745, "author": "Benjamin Franklin"},
        "category": "finance",
        "domains": ["finance", "physics", "hydrology"],
        "axes": ["conservation_balance", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Compound erosion: $5/day = $1,825/year = $54,750 over 30 years (undiscounted). Invested at 5% real return: ~$127,000. The 'small' expense compounds into a major loss of future optionality. Literal naval engineering: a 1 cm² hole 2 m below waterline admits ~7 L/sec; an unattended bilge fills a 50-ton vessel in hours.",
        "wisdom": "Small recurring drains beat single large purchases on lifetime cost. The Shepherd brings this when the user is focused on cutting one big expense while ten small ones bleed steadily. Audit the recurring; the one-time will mostly take care of itself.",
        "triggers": {"keywords": ["small leak", "little expenses", "compound erosion", "Franklin", "subscriptions"], "axes": ["conservation_balance"]},
    },
    {
        "id": "saying_franklin_ounce_prevention",
        "kind": "saying",
        "title": "An ounce of prevention is worth a pound of cure",
        "saying": "An ounce of prevention is worth a pound of cure.",
        "source": {"publication": "Pennsylvania Gazette letter, Franklin (1736)", "year": 1736, "author": "Benjamin Franklin"},
        "category": "medicine",
        "domains": ["medicine", "operations_research", "economics"],
        "axes": ["time_sequence", "conservation_balance", "metabolism"],
        "verdict": "CONFIRMED",
        "verification": "Prevention-to-treatment cost ratios in modern medicine often exceed 1:16 (the 'ounce' to the 'pound'). Childhood vaccination: ~1:14 (CDC). Lead-paint abatement: ~1:200 (cognitive-deficit cost averaged). Sanitation: orders of magnitude. Franklin's intuition, formed about fire prevention in 1736, is one of the most quantitatively robust observations in public-health economics.",
        "wisdom": "Prevention pays. The Shepherd brings this for water-safe practices, vaccination, sanitation, food handling, fire codes, brake pad replacement, dental flossing — every place a small habit averts a large catastrophe.",
        "triggers": {"keywords": ["ounce of prevention", "Franklin", "preventive medicine", "fire prevention"], "axes": ["time_sequence", "conservation_balance"]},
    },
    {
        "id": "saying_franklin_eat_to_live",
        "kind": "saying",
        "title": "Eat to live, and not live to eat",
        "saying": "Eat to live, and not live to eat.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1733, "author": "Benjamin Franklin"},
        "category": "nutrition",
        "domains": ["nutrition", "medicine", "exercise_science"],
        "axes": ["metabolism", "phase"],
        "verdict": "CONFIRMED",
        "verification": "Hedonic-eating biomarkers correlate with metabolic syndrome (obesity, insulin resistance, hypertension, dyslipidemia). Time-restricted feeding (eating windows ≤10h) and caloric restriction without malnutrition both show measurable benefits in cardiovascular, glycemic, and longevity markers across human and animal studies.",
        "wisdom": "Eating as fuel keeps the body running; eating as entertainment crowds out everything fuel-related. The Shepherd brings this not as moralism but as physics: the body has a metabolic ceiling, and the cost of breaching it is paid later, in years.",
        "triggers": {"keywords": ["eat to live", "Franklin", "moderation", "metabolic health"], "axes": ["metabolism"]},
    },
    {
        "id": "saying_franklin_no_gains",
        "kind": "saying",
        "title": "There are no gains without pains",
        "saying": "There are no gains without pains.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1745, "author": "Benjamin Franklin"},
        "category": "health",
        "domains": ["exercise_science", "phase"],
        "axes": ["metabolism", "time_sequence"],
        "verdict": "MIXED",
        "verification": "Physiology: largely true. Muscle hypertrophy requires progressive overload past steady-state; cardiovascular adaptation requires HR sustained above resting baseline; bone density requires impact loading. *Pain* in the soreness sense is partly a marker of training stimulus, partly damage. Skill acquisition: the aphorism overstates — deliberate practice involves discomfort and failure but not necessarily pain. Beware overtraining.",
        "wisdom": "Adaptation requires stress; without stress, no growth. The Shepherd carries this for fitness, learning, and craft — pairs it with the protocol about recovery (stress + rest is what builds; stress without rest only breaks).",
        "triggers": {"keywords": ["no gains without pains", "Franklin", "exercise", "deliberate practice"], "axes": ["metabolism", "time_sequence"]},
    },
    {
        "id": "saying_franklin_well_dry",
        "kind": "saying",
        "title": "When the well's dry, we know the worth of water",
        "saying": "When the well's dry, we know the worth of water.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1746, "author": "Benjamin Franklin"},
        "category": "economics",
        "domains": ["economics", "philosophy", "hydrology"],
        "axes": ["conservation_balance", "time_sequence", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Behavioral economics calls this 'endowment loss-aversion': humans systematically underweight what they have and overweight what they lose. Replication across hundreds of studies. The opposite error is rarer: we don't typically over-value what's freely available, only under-value it until it's gone.",
        "wisdom": "Audit what you'd miss before you lose it. The Shepherd brings this when the user is about to dismiss something abundant — health, time with the living, a working tool, daily bread — that becomes precious only when scarce.",
        "triggers": {"keywords": ["well's dry", "Franklin", "endowment effect", "value scarcity"], "axes": ["conservation_balance"]},
    },
    {
        "id": "saying_franklin_plough_deep",
        "kind": "saying",
        "title": "Plough deep, while sluggards sleep",
        "saying": "Plough deep, while sluggards sleep, and you shall have corn to sell and to keep.",
        "source": {"publication": "Poor Richard's Almanack ('Way to Wealth' preface)", "year": 1758, "author": "Benjamin Franklin"},
        "category": "agriculture",
        "domains": ["agriculture", "soil_science", "phase"],
        "axes": ["metabolism", "time_sequence", "physical_substance"],
        "verdict": "MIXED",
        "verification": "Deep-ploughing dogma served 18th-c. mouldboard agriculture, where shallow soils were turned to access fertility and bury weed seed. Modern soil science calls it backward: deep tillage destroys soil structure, oxidizes organic matter, increases erosion. The Dust Bowl was deep ploughing at scale. Modern no-till + cover crops outproduces deep tillage on the same field over a decade. Franklin's metaphor (work harder than the lazy) survives; the literal agronomy doesn't.",
        "wisdom": "Sometimes the old practice that worked under old conditions becomes a textbook wrong under new ones. The Shepherd brings this whenever the user invokes 'the old ways' — sometimes the old ways are right (lacto-fermentation, composting, hand tools); sometimes they're a Dust Bowl waiting for wind.",
        "triggers": {"keywords": ["plough deep", "tillage", "Franklin", "Way to Wealth", "no-till"], "axes": ["metabolism", "time_sequence"]},
    },
    {
        "id": "saying_franklin_write_worth",
        "kind": "saying",
        "title": "Write things worth reading, or do things worth the writing",
        "saying": "If you would not be forgotten as soon as you are dead and rotten, either write things worth reading, or do things worth the writing.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1738, "author": "Benjamin Franklin"},
        "category": "philosophy",
        "domains": ["philosophy", "information_theory", "history"],
        "axes": ["information_encoding", "time_sequence", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Information-theoretic durability: signals survive only if they're encoded redundantly enough to outlast their carriers. Either you write durable text (encoding) or you do durable deeds (others encode you). Anonymity correlates with extinction in the historical record. Franklin's framing predates Claude Shannon's information theory by 210 years and reaches the same conclusion.",
        "wisdom": "Two paths to memory: the encoded text or the deed-others-record. The Shepherd brings this when the user is debating whether their work matters — the work is the storage medium. The keeping is the substrate.",
        "triggers": {"keywords": ["write worth reading", "do worth writing", "Franklin", "legacy", "encoding"], "axes": ["information_encoding", "time_sequence"]},
    },
    {
        "id": "saying_franklin_fish_visitors",
        "kind": "saying",
        "title": "Fish and visitors stink after three days",
        "saying": "Fish and visitors stink after three days.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1736, "author": "Benjamin Franklin"},
        "category": "biology",
        "domains": ["biology", "nutrition"],
        "axes": ["metabolism", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Fish: yes, mechanistically. Fresh fish at 4°C develops trimethylamine and putrescine compounds within 48–72 hours from enzymatic and microbial post-mortem changes. Stored at 0°C (on ice), edible window extends to 5–7 days. Visitors: depends on the visitor; Franklin's joke remains funny because the half-life of polite hospitality is genuinely shorter than people predict at the threshold.",
        "wisdom": "Spoilage curves are predictable. The Shepherd brings this for the fish claim (ice-store, freeze, or salt-cure by day 2 if you can't eat it) and acknowledges the joke about the visitors as observed wisdom about humans, not a verifier output.",
        "triggers": {"keywords": ["fish stink", "Franklin", "fish storage", "spoilage", "hospitality"], "axes": ["metabolism", "time_sequence"]},
    },
    {
        "id": "saying_franklin_lie_dogs",
        "kind": "saying",
        "title": "He that lieth down with dogs, shall rise up with fleas",
        "saying": "He that lieth down with dogs, shall rise up with fleas.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1733, "author": "Benjamin Franklin"},
        "category": "biology",
        "domains": ["biology", "medicine"],
        "axes": ["metabolism", "physical_substance", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Literal biology: Ctenocephalides felis (cat flea, the species that mainly bites dogs and humans) transfers readily from host to bed-sharer. Vector for typhus, plague, tapeworm. Metaphorical: behavioral / reputational contagion from sustained company is well-documented (Christakis & Fowler, *Connected*; ~3-degree influence on smoking, obesity, happiness).",
        "wisdom": "Proximity transmits — pathogens, habits, reputations. The Shepherd brings this when the user is asking about influence: the company you keep both literally and figuratively shapes the body and the soul.",
        "triggers": {"keywords": ["lie down with dogs", "fleas", "Franklin", "behavioral contagion", "social influence"], "axes": ["metabolism", "physical_substance"]},
    },
    {
        "id": "saying_franklin_necessity_bargain",
        "kind": "saying",
        "title": "Necessity never made a good bargain",
        "saying": "Necessity never made a good bargain.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1735, "author": "Benjamin Franklin"},
        "category": "economics",
        "domains": ["economics", "finance", "rhetoric"],
        "axes": ["authority_trust", "conservation_balance", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Negotiation theory: BATNA (best alternative to a negotiated agreement) determines bargaining strength. Necessity = no alternative = no leverage. Empirically, urgency-pressured purchases (rushed real estate, distressed sales, payday loans at 400% APR) realize 20–80% worse outcomes than the same transaction with time.",
        "wisdom": "Reservoir is leverage. The Shepherd brings this when the user is about to negotiate from a position of need — and notes that the way to fix a weak position is rarely better technique; it's a better BATNA. Build the alternative; then negotiate.",
        "triggers": {"keywords": ["necessity bargain", "Franklin", "BATNA", "negotiation", "urgency"], "axes": ["authority_trust", "conservation_balance"]},
    },
    {
        "id": "saying_franklin_well_done",
        "kind": "saying",
        "title": "Well done is better than well said",
        "saying": "Well done is better than well said.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1737, "author": "Benjamin Franklin"},
        "category": "rhetoric",
        "domains": ["rhetoric", "philosophy"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Signal-theoretic: speech is cheap (low cost to produce), action is costly. Costly signals are more reliable indicators of underlying state than cheap signals. Trust calibrated on behavior outperforms trust calibrated on speech in repeated games (Axelrod's tournaments, Ostrom's commons fieldwork). Almost identical to James 2:18 ('Show me your faith without thy works...').",
        "wisdom": "Action is a costly signal; words are not. The Shepherd brings this when the user is choosing whether to announce what they intend or to do it. Generally: do it, then say what you did. Speech before action commits future-you against your interest.",
        "triggers": {"keywords": ["well done", "actions speak", "Franklin", "costly signaling"], "axes": ["authority_trust"]},
    },
    {
        "id": "saying_franklin_used_key",
        "kind": "saying",
        "title": "The used key is always bright",
        "saying": "The used key is always bright.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1744, "author": "Benjamin Franklin"},
        "category": "physics",
        "domains": ["chemistry", "physics", "manufacturing"],
        "axes": ["physical_substance", "metabolism", "time_sequence"],
        "verdict": "CONFIRMED",
        "verification": "Literal metallurgy: friction abrades oxidation products from contact surfaces; an unused key oxidizes (Cu→Cu₂O→CuO; brass tarnishes), a used key gets its surface continually polished by lock contact. Same principle as cast-iron seasoning, well-used tools, well-used joints in the body, and well-used skills in the brain: regular use prevents decay.",
        "wisdom": "Use is what keeps a thing alive. The Shepherd brings this for tools, skills, relationships, languages, instruments — anything that decays through neglect and renews through routine application.",
        "triggers": {"keywords": ["used key bright", "Franklin", "use it or lose it", "oxidation"], "axes": ["physical_substance", "metabolism"]},
    },
    {
        "id": "saying_franklin_god_helps",
        "kind": "saying",
        "title": "God helps them that help themselves",
        "saying": "God helps them that help themselves.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1736, "author": "Benjamin Franklin"},
        "category": "theology",
        "domains": ["theology", "philosophy", "scripture"],
        "axes": ["authority_trust", "metabolism"],
        "verdict": "MIXED",
        "verification": "Often quoted as Scripture; isn't. The proverb is Aesopic ('Hercules and the Waggoner') popularized by Franklin. Scripture is more nuanced: 'I can do all things through Christ which strengtheneth me' (Phil 4:13) couples human effort to divine power, but the Sermon on the Mount expressly rebukes self-sufficiency (Matt 5:3, 'Blessed are the poor in spirit'). The aphorism captures part of the Christian tradition (faith and works together — James 2:17) and risks misleading the part about grace being unearned.",
        "wisdom": "Half a truth dressed as Scripture. The Shepherd brings this with the caveat that grace is unearned, while faithfulness includes acting. The right framing is Phil 2:12–13: 'work out your salvation … for it is God which worketh in you'. Both, not one.",
        "triggers": {"keywords": ["God helps", "self-help", "Franklin", "James 2:17", "Phil 2:13"], "axes": ["authority_trust"]},
    },
    {
        "id": "saying_franklin_borrow_sorrow",
        "kind": "saying",
        "title": "He that goes a-borrowing, goes a-sorrowing",
        "saying": "He that goes a-borrowing, goes a-sorrowing.",
        "source": {"publication": "Poor Richard's Almanack ('Way to Wealth' preface)", "year": 1758, "author": "Benjamin Franklin"},
        "category": "finance",
        "domains": ["finance", "economics"],
        "axes": ["authority_trust", "time_sequence", "conservation_balance"],
        "verdict": "MIXED",
        "verification": "Consumer debt: largely true. Average US credit-card APR ~22% (2026); compound interest on revolving balance erodes net worth aggressively. Productive debt (mortgage on appreciating asset, business loan with positive ROI > rate, education with calculable wage uplift): can be net-positive. The aphorism is right about debt for consumption, oversold about debt for production.",
        "wisdom": "Debt for consumption vs. debt for production are different species. The Shepherd brings this when the user is debating a loan — and asks which side it's on: does the borrowed dollar produce more than its interest cost, or does it disappear?",
        "triggers": {"keywords": ["borrow sorrow", "Franklin", "consumer debt", "productive debt"], "axes": ["authority_trust", "time_sequence"]},
    },
    {
        "id": "saying_franklin_fail_prepare",
        "kind": "saying",
        "title": "By failing to prepare, you are preparing to fail",
        "saying": "By failing to prepare, you are preparing to fail.",
        "source": {"publication": "attributed to Franklin (Poor Richard's tradition)", "year": 1758, "author": "Benjamin Franklin (attributed)"},
        "category": "reasoning",
        "domains": ["operations_research", "phase"],
        "axes": ["time_sequence", "reasoning"],
        "verdict": "CONFIRMED",
        "verification": "Operations research: cost of preparation is bounded; cost of recovery from failure is heavy-tailed. Expected cost of unprepared failure dominates expected cost of prepared success-and-failure mix for nearly all real-world action surfaces. Modern reliability engineering (FMEA, fault trees, premortems) is institutionalized version. Note: this exact wording is attributed to Franklin but uncertain; the spirit is Poor-Richard-authentic.",
        "wisdom": "Preparation is cheap insurance against heavy-tail failure. The Shepherd brings this when the user is about to act without a plan — and asks what failure looks like and whether it's recoverable.",
        "triggers": {"keywords": ["failing to prepare", "Franklin", "premortem", "FMEA"], "axes": ["time_sequence", "reasoning"]},
    },
    {
        "id": "saying_franklin_wealth_enjoy",
        "kind": "saying",
        "title": "Wealth is not his that has it, but his that enjoys it",
        "saying": "Wealth is not his that has it, but his that enjoys it.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1736, "author": "Benjamin Franklin"},
        "category": "philosophy",
        "domains": ["economics", "philosophy", "nutrition"],
        "axes": ["conservation_balance", "metabolism"],
        "verdict": "CONFIRMED",
        "verification": "Utility theory: marginal utility of additional wealth decreases sharply past meeting basic needs (Kahneman/Deaton 2010 found ~$75k US satiation point for emotional wellbeing). Wealth stored without conversion to use yields no utility. The 'wealth' that matters is what's been turned into nourishment, freedom, relationship, or generosity.",
        "wisdom": "Wealth is a potential-energy variable; until converted to actual flourishing (or given), it does nothing. The Shepherd brings this when the user has confused accumulation with the thing accumulated FOR.",
        "triggers": {"keywords": ["wealth enjoys", "Franklin", "marginal utility", "hoarding"], "axes": ["conservation_balance", "metabolism"]},
    },
    {
        "id": "saying_franklin_experience_school",
        "kind": "saying",
        "title": "Experience keeps a dear school, yet fools will learn in no other",
        "saying": "Experience keeps a dear school, yet fools will learn in no other.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1743, "author": "Benjamin Franklin"},
        "category": "reasoning",
        "domains": ["phase", "operations_research", "philosophy"],
        "axes": ["time_sequence", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Learning by failure is informationally rich but financially / emotionally expensive. Vicarious learning (from history, books, others' failure) is cheaper but lower-bandwidth. Optimal mix is dominated by vicarious for low-cost-of-failure domains and direct for high-cost domains (e.g., skin in the game per Taleb). The 'fool' in the aphorism is the person who insists on full-cost tuition where reading the casebook would have sufficed.",
        "wisdom": "Read the casebook before you become the case. The Shepherd brings this when the user is about to repeat a mistake the keeping has already recorded — Foxfire, Poor Richard's, the almanac entries, the engine's own misalignments lens.",
        "triggers": {"keywords": ["experience dear school", "Franklin", "learning from failure", "vicarious learning"], "axes": ["time_sequence", "authority_trust"]},
    },
    {
        "id": "saying_franklin_half_truth",
        "kind": "saying",
        "title": "Half the truth is often a great lie",
        "saying": "Half the truth is often a great lie.",
        "source": {"publication": "Poor Richard's Almanack", "year": 1758, "author": "Benjamin Franklin"},
        "category": "rhetoric",
        "domains": ["rhetoric", "information_theory", "philosophy"],
        "axes": ["information_encoding", "authority_trust"],
        "verdict": "CONFIRMED",
        "verification": "Information-theoretic: omission is a high-leverage rhetorical lever because the recipient updates as if they have full data. Selective truth (cherry-picking) is the dominant manipulation pattern in advertising, political messaging, and statistical communication. Modern formal version: 'You shall not bear false witness' (Ex 20:16) is read in Reformed and Jewish ethics to include misleading omission, not only outright fabrication.",
        "wisdom": "Truth is a closed set; partial truth opens it back up. The Shepherd brings this for evaluating sources, framing user-asked questions, and reading the engine's own outputs — what wasn't said is often the answer.",
        "triggers": {"keywords": ["half truth", "Franklin", "lies of omission", "cherry picking"], "axes": ["information_encoding", "authority_trust"]},
    },
    {
        "id": "saying_franklin_haste_make",
        "kind": "saying",
        "title": "Time is money",
        "saying": "Remember that time is money.",
        "source": {"publication": "Advice to a Young Tradesman, Franklin (1748)", "year": 1748, "author": "Benjamin Franklin"},
        "category": "economics",
        "domains": ["economics", "finance", "labor"],
        "axes": ["time_sequence", "conservation_balance"],
        "verdict": "MIXED",
        "verification": "True at the margin (opportunity cost of an hour spent vs. an hour earning), false at the limit (time has dimensions money does not: irreversibility, relational, sacred). Franklin's framing has fueled American productivity culture AND its discontents. Optimum: time has a money-shadow on transactional surfaces and a different metric (presence, faithfulness, rest) on relational and sabbath surfaces. The mark of wisdom is knowing which surface you're on.",
        "wisdom": "Time has a money-price in commerce and no price at all in prayer, presence, and rest. The Shepherd brings this when the user is about to monetize an hour that belongs to a different ledger.",
        "triggers": {"keywords": ["time is money", "Franklin", "opportunity cost", "sabbath"], "axes": ["time_sequence", "conservation_balance"]},
    },
]


def main() -> int:
    if not ALMANAC.exists():
        print(f"ERROR: almanac file not found at {ALMANAC}")
        return 1

    existing: set[str] = set()
    with ALMANAC.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass

    to_write = [e for e in ENTRIES if e["id"] not in existing]
    skipped = [e["id"] for e in ENTRIES if e["id"] in existing]
    if skipped:
        print(f"skipping (already present): {len(skipped)}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            v = e["verdict"]
            print(f"  + {e['id']:42s}  {v}")

    print(f"\n-- appended {len(to_write)} Poor Richard's entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

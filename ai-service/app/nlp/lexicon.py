"""Bilingual agricultural lexicon backing the NLP pipeline (Section 4.1).

Everything here is deterministic data: intent trigger words, the Hindi/English
crop vocabulary mapped onto Agmarknet commodity names, unit synonyms, and a
gazetteer of the Hindi-belt states and districts the system targets.
"""

from __future__ import annotations

# --- Section 4.1.2: intent trigger vocabulary -------------------------------
# Weight 2 terms are strong signals; weight 1 terms are supporting context.
INTENT_TRIGGERS: dict[str, dict[str, int]] = {
    "price_query": {
        "price": 2, "rate": 2, "cost": 2, "bhav": 2, "kitna": 1, "value": 1,
        # "selling for" is a price idiom, not a sell question. It has to outrank
        # the bare "sell" trigger or "how much are tomatoes selling for" is
        # classified as sell_advice.
        "selling for": 4, "how much": 2, "how much does": 3, "what is the price": 3,
        "भाव": 2, "रेट": 2, "कीमत": 2, "दाम": 2, "मूल्य": 2, "कितना": 1,
        # "क्या" is deliberately absent: it is a bare interrogative that opens
        # sell and trend questions just as often as price ones, and crediting
        # it here produced ties that the default intent then won.
    },
    "buyer_search": {
        "buyer": 2, "buyers": 2, "buying": 2, "purchase": 2, "trader": 2, "traders": 2,
        "kharid": 2, "mandi contact": 2, "apmc": 2, "who is buying": 3, "nearby": 1,
        "खरीद": 2, "खरीदार": 2, "व्यापारी": 2, "कौन": 1, "आसपास": 1, "संपर्क": 1,
        # Maithili/Bhojpuri future forms of "to buy": केओ किनत, के कीनी.
        "किनत": 3, "किनैत": 3, "कीनत": 3, "कीनी": 2,
    },
    "sell_advice": {
        "should i sell": 3, "sell now": 3, "sell or wait": 3, "bech": 2,
        "sell": 2, "wait": 2, "advice": 2, "hold": 2, "profit": 1,
        "should i wait": 4, "should i hold": 4,
        # An explicit first-person sell verb is a strong signal, and has to beat
        # the price noun that almost always appears alongside it.
        "बेचूं": 4, "बेच दूं": 4, "बेच दें": 4, "बेचब": 3, "बेचीं": 3, "विकू": 4, "विक्री": 3,
        "बेच": 2, "बेचना": 3, "रुकूं": 3, "इंतजार": 2, "सलाह": 2, "चाहिए": 1,
        "थांबू": 3, "বিক্রি": 3, "விற்க": 3, "விற்பனை": 3,
    },
    "trend_analysis": {
        "trend": 3, "forecast": 4, "rising": 3, "falling": 3, "increase": 2, "decrease": 2,
        "last week": 3, "last month": 3, "next week": 3, "history": 2, "compare": 1,
        "going up": 3, "going down": 3,
        # Words that denote a *change* in price, as opposed to its level. Without
        # a higher weight these tie with the price noun in the same sentence
        # ("गेहूं का भाव घटा है") and the query is read as a price question.
        "बढ़ा": 3, "घटा": 3, "बढ़ रहा": 3, "घट रहा": 3, "बढ़ल": 3, "घटल": 3,
        "वाढला": 3, "बेड़েছে": 3, "उयर्न्द": 3,
        "रुझान": 3, "तेजी": 3, "मंदी": 3, "कल": 2,
        "पिछले": 2, "पिछला": 2, "पछिला": 2, "मागील": 2, "हफ्ते": 2, "सप्ताह": 2, "महीने": 2,
        "पिछले हफ्ते": 4, "पिछले महीने": 4, "कैसा रहा": 3,
    },
}

DEFAULT_INTENT = "price_query"

# --- Section 4.1.3: crop vocabulary -----------------------------------------
# Agmarknet commodity name -> accepted surface forms (Hindi, English, dialect).
CROP_VOCABULARY: dict[str, list[str]] = {
    "Tomato": ["tomato", "tamatar", "टमाटर", "टमाटार"],
    "Onion": ["onion", "pyaz", "pyaaz", "kanda", "प्याज", "प्याज़", "कांदा"],
    "Wheat": ["wheat", "gehu", "gehun", "gahu", "गेहूं", "गेहूँ", "गेहू"],
    "Potato": ["potato", "aloo", "alu", "आलू"],
    "Rice": ["rice", "chawal", "dhan", "paddy", "चावल", "धान"],
    "Lentil (Masur)(Whole)": ["lentil", "masur", "masoor", "मसूर", "दाल"],
    "Maize": ["maize", "makka", "corn", "मक्का", "मकई"],
    "Mustard": ["mustard", "sarson", "सरसों", "सरसो"],
    "Bengal Gram (Gram)(Whole)": ["gram", "chana", "चना"],
    "Sugarcane": ["sugarcane", "ganna", "गन्ना"],
    "Cauliflower": ["cauliflower", "phool gobhi", "फूल गोभी", "गोभी"],
    "Brinjal": ["brinjal", "baingan", "eggplant", "बैंगन"],
    "Garlic": ["garlic", "lehsun", "लहसुन"],
    "Green Chilli": ["chilli", "mirch", "mirchi", "मिर्च", "मिर्ची"],
    "Soyabean": ["soyabean", "soybean", "soya", "सोयाबीन"],
}

# Canonical Devanagari label used when answering in Hindi.
CROP_HINDI_LABEL: dict[str, str] = {
    "Tomato": "टमाटर",
    "Onion": "प्याज",
    "Wheat": "गेहूं",
    "Potato": "आलू",
    "Rice": "चावल",
    "Lentil (Masur)(Whole)": "मसूर",
    "Maize": "मक्का",
    "Mustard": "सरसों",
    "Bengal Gram (Gram)(Whole)": "चना",
    "Sugarcane": "गन्ना",
    "Cauliflower": "फूल गोभी",
    "Brinjal": "बैंगन",
    "Garlic": "लहसुन",
    "Green Chilli": "हरी मिर्च",
    "Soyabean": "सोयाबीन",
}

# --- Quantity units ---------------------------------------------------------
# Normalised unit -> surface forms.  Conversion factors are to quintals, the
# unit Agmarknet reports modal price in.
UNIT_SYNONYMS: dict[str, list[str]] = {
    "quintal": ["quintal", "qtl", "क्विंटल", "कुंतल"],
    "kg": ["kg", "kilo", "kilogram", "किलो", "किग्रा"],
    "ton": ["ton", "tonne", "टन"],
    "maund": ["maund", "man", "मन"],
}

UNIT_TO_QUINTAL: dict[str, float] = {
    "quintal": 1.0,
    "kg": 0.01,
    "ton": 10.0,
    "maund": 0.373,
}

# --- Gazetteer of the targeted Hindi belt (Section 1.4) ---------------------
STATE_DISTRICTS: dict[str, list[str]] = {
    "Bihar": [
        "Patna", "Muzaffarpur", "Gaya", "Bhagalpur", "Nalanda", "Vaishali",
        "Darbhanga", "Purnia", "Saran", "Samastipur", "Begusarai", "Rohtas",
    ],
    "Uttar Pradesh": [
        "Lucknow", "Kanpur", "Varanasi", "Agra", "Meerut", "Gorakhpur",
        "Prayagraj", "Bareilly", "Aligarh", "Moradabad", "Jhansi",
    ],
    "Madhya Pradesh": [
        "Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar",
        "Rewa", "Satna", "Dewas", "Ratlam",
    ],
    "Punjab": [
        "Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
        "Mohali", "Hoshiarpur", "Moga", "Ferozepur",
    ],
    "Haryana": ["Karnal", "Hisar", "Rohtak", "Panipat", "Ambala", "Sirsa"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Ajmer", "Bikaner", "Udaipur"],
}

# --- Place names, per script (Section 6.3) ----------------------------------
# A Bengali or Tamil farmer names their district in their own script, so a
# Devanagari-only gazetteer silently fails to resolve their location and quietly
# falls back to the default districts. Each canonical name therefore carries a
# form in every script the system reads.
#
# Only the citation form is listed. Case endings attach as suffixes in these
# languages (পাটনা -> পাটনায়, பாட்னா -> பாட்னாவில்), and the matcher accepts a
# following non-ASCII character, so the inflected forms resolve too.
PLACE_NAMES: dict[str, dict[str, str]] = {
    # States
    "Bihar": {"deva": "बिहार", "beng": "বিহার", "taml": "பீகார்"},
    "Uttar Pradesh": {"deva": "उत्तर प्रदेश", "beng": "উত্তরপ্রদেশ", "taml": "உத்தரப்பிரதேசம்"},
    "Madhya Pradesh": {"deva": "मध्य प्रदेश", "beng": "মধ্যপ্রদেশ", "taml": "மத்தியப்பிரதேசம்"},
    "Punjab": {"deva": "पंजाब", "beng": "পাঞ্জাব", "taml": "பஞ்சாப்"},
    "Haryana": {"deva": "हरियाणा", "beng": "হরিয়ানা", "taml": "ஹரியானா"},
    "Rajasthan": {"deva": "राजस्थान", "beng": "রাজস্থান", "taml": "ராஜஸ்தான்"},
    # Districts
    "Patna": {"deva": "पटना", "beng": "পাটনা", "taml": "பாட்னா"},
    "Muzaffarpur": {"deva": "मुजफ्फरपुर", "beng": "মুজাফফরপুর", "taml": "முசாபர்பூர்"},
    "Gaya": {"deva": "गया", "beng": "গয়া", "taml": "கயா"},
    "Bhagalpur": {"deva": "भागलपुर", "beng": "ভাগলপুর", "taml": "பாகல்பூர்"},
    "Nalanda": {"deva": "नालंदा", "beng": "নালন্দা", "taml": "நாளந்தா"},
    "Vaishali": {"deva": "वैशाली", "beng": "বৈশালী", "taml": "வைசாலி"},
    "Darbhanga": {"deva": "दरभंगा", "beng": "দারভাঙ্গা", "taml": "தர்பங்கா"},
    "Purnia": {"deva": "पूर्णिया", "beng": "পূর্ণিয়া", "taml": "பூர்ணியா"},
    "Lucknow": {"deva": "लखनऊ", "beng": "লখনউ", "taml": "லக்னோ"},
    "Kanpur": {"deva": "कानपुर", "beng": "কানপুর", "taml": "கான்பூர்"},
    "Varanasi": {"deva": "वाराणसी", "beng": "বারাণসী", "taml": "வாரணாசி"},
    "Gorakhpur": {"deva": "गोरखपुर", "beng": "গোরখপুর", "taml": "கோரக்பூர்"},
    "Agra": {"deva": "आगरा", "beng": "আগ্রা", "taml": "ஆக்ரா"},
    "Bhopal": {"deva": "भोपाल", "beng": "ভোপাল", "taml": "போபால்"},
    "Indore": {"deva": "इंदौर", "beng": "ইন্দোর", "taml": "இந்தூர்"},
    "Jabalpur": {"deva": "जबलपुर", "beng": "জবলপুর", "taml": "ஜபல்பூர்"},
    "Ludhiana": {"deva": "लुधियाना", "beng": "লুধিয়ানা", "taml": "லுதியானா"},
    "Amritsar": {"deva": "अमृतसर", "beng": "অমৃতসর", "taml": "அமிர்தசரஸ்"},
    "Patiala": {"deva": "पटियाला", "beng": "পাটিয়ালা", "taml": "பாட்டியாலா"},
    "Karnal": {"deva": "करनाल", "beng": "কারনাল", "taml": "கர்னால்"},
    "Jaipur": {"deva": "जयपुर", "beng": "জয়পুর", "taml": "ஜெய்ப்பூர்"},
}

# Short forms and colloquial variants that map onto the same canonical name.
PLACE_SHORT_FORMS: dict[str, str] = {
    "यूपी": "Uttar Pradesh",
    "एमपी": "Madhya Pradesh",
    "बिहार राज्य": "Bihar",
}

# Dependent vowel signs and the virama/pulli, which case endings replace rather
# than follow. Tamil பீகார் + இல் becomes பீகாரில் — the pulli is dropped, so the
# citation form is not a prefix of the inflected one and plain containment misses
# it. Stripping the trailing mark gives a stem that does match.
_PLACE_FINAL_MARKS = "\u0BCD\u094D\u09CD" + "ािीुूृेैोौंँः্ািীুূেৈোৌংாிீுூெேைொோௌ"


def _place_stem(form: str) -> str | None:
    stem = form.rstrip(_PLACE_FINAL_MARKS)
    return stem if len(stem) >= 3 and stem != form else None


# alias -> canonical, across every script. Built once at import.
PLACE_ALIASES: dict[str, str] = dict(PLACE_SHORT_FORMS)
for _canonical, _forms in PLACE_NAMES.items():
    for _form in _forms.values():
        PLACE_ALIASES[_form] = _canonical
        _stem = _place_stem(_form)
        # setdefault so a stem never shadows another place's citation form.
        if _stem:
            PLACE_ALIASES.setdefault(_stem, _canonical)
del _canonical, _forms, _form

# Language code -> the script key its place names are written in.
LANGUAGE_SCRIPT: dict[str, str] = {
    "hi": "deva", "bho": "deva", "mai": "deva", "mr": "deva",
    "bn": "beng", "ta": "taml", "en": "latin",
}

# --- Pincode prefix -> (state, district) ------------------------------------
# First three digits are enough to place a pincode inside a postal region.
PINCODE_PREFIXES: dict[str, tuple[str, str]] = {
    "800": ("Bihar", "Patna"),
    "801": ("Bihar", "Patna"),
    "802": ("Bihar", "Rohtas"),
    "823": ("Bihar", "Gaya"),
    "812": ("Bihar", "Bhagalpur"),
    "842": ("Bihar", "Muzaffarpur"),
    "803": ("Bihar", "Nalanda"),
    "844": ("Bihar", "Vaishali"),
    "846": ("Bihar", "Darbhanga"),
    "854": ("Bihar", "Purnia"),
    "226": ("Uttar Pradesh", "Lucknow"),
    "208": ("Uttar Pradesh", "Kanpur"),
    "221": ("Uttar Pradesh", "Varanasi"),
    "282": ("Uttar Pradesh", "Agra"),
    "273": ("Uttar Pradesh", "Gorakhpur"),
    "462": ("Madhya Pradesh", "Bhopal"),
    "452": ("Madhya Pradesh", "Indore"),
    "482": ("Madhya Pradesh", "Jabalpur"),
    "141": ("Punjab", "Ludhiana"),
    "143": ("Punjab", "Amritsar"),
    "147": ("Punjab", "Patiala"),
    "132": ("Haryana", "Karnal"),
    "302": ("Rajasthan", "Jaipur"),
}

# --- Approximate district centroids for GPS resolution ----------------------
DISTRICT_CENTROIDS: dict[tuple[str, str], tuple[float, float]] = {
    ("Bihar", "Patna"): (25.5941, 85.1376),
    ("Bihar", "Muzaffarpur"): (26.1209, 85.3647),
    ("Bihar", "Gaya"): (24.7955, 84.9994),
    ("Bihar", "Bhagalpur"): (25.2425, 86.9842),
    ("Bihar", "Nalanda"): (25.1979, 85.5232),
    ("Bihar", "Vaishali"): (25.6840, 85.2130),
    ("Bihar", "Darbhanga"): (26.1542, 85.8918),
    ("Bihar", "Purnia"): (25.7771, 87.4753),
    ("Uttar Pradesh", "Lucknow"): (26.8467, 80.9462),
    ("Uttar Pradesh", "Kanpur"): (26.4499, 80.3319),
    ("Uttar Pradesh", "Varanasi"): (25.3176, 82.9739),
    ("Uttar Pradesh", "Agra"): (27.1767, 78.0081),
    ("Uttar Pradesh", "Gorakhpur"): (26.7606, 83.3732),
    ("Madhya Pradesh", "Bhopal"): (23.2599, 77.4126),
    ("Madhya Pradesh", "Indore"): (22.7196, 75.8577),
    ("Madhya Pradesh", "Jabalpur"): (23.1815, 79.9864),
    ("Punjab", "Ludhiana"): (30.9010, 75.8573),
    ("Punjab", "Amritsar"): (31.6340, 74.8723),
    ("Punjab", "Patiala"): (30.3398, 76.3869),
    ("Haryana", "Karnal"): (29.6857, 76.9905),
    ("Rajasthan", "Jaipur"): (26.9124, 75.7873),
}


def localise_place(name: str | None, language: str = "hi") -> str | None:
    """Render a state or district in the script of the given language.

    Falls back to the canonical English spelling when no form is known, which
    is also what English itself gets. Mandi names are deliberately *not* passed
    through here: a farmer looks for the name painted on the yard gate, not a
    transliteration of it.
    """
    if not name:
        return name
    script = LANGUAGE_SCRIPT.get(language, "deva")
    if script == "latin":
        return name
    return PLACE_NAMES.get(name, {}).get(script, name)


def to_devanagari_place(name: str | None) -> str | None:
    """Devanagari form of a place. Retained for callers that assume Hindi."""
    return localise_place(name, "hi")


def all_districts() -> list[tuple[str, str]]:
    """Every (state, district) pair known to the gazetteer."""
    return [(state, d) for state, districts in STATE_DISTRICTS.items() for d in districts]


def crop_from_surface_form(token: str) -> str | None:
    """Resolve a single surface form to its Agmarknet commodity name."""
    needle = token.strip().lower()
    for commodity, forms in CROP_VOCABULARY.items():
        if needle in forms:
            return commodity
    return None

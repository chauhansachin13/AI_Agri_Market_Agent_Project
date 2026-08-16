"""Labelled evaluation set for the NLP pipeline.

Section 5.2 of the report quotes accuracy figures for intent classification,
crop detection and location resolution. This is the held-out set those numbers
are measured on, so the claims in the README are reproducible rather than
asserted.

Coverage is deliberately uneven in the way real traffic is uneven: mostly
straightforward questions, plus a tail of the things that actually break
parsers — code-switching, plurals, case inflection, dialect vocabulary,
questions with no location, and questions that sit between two intents.

Each case carries only the labels it is testing. `crop=None` means "no crop
should be detected"; a missing key means the field is not under test.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    query: str
    language: str
    intent: str
    crop: str | None = None
    state: str | None = None
    district: str | None = None
    # Set for queries a human would also find genuinely ambiguous; they are
    # reported separately so they neither flatter nor unfairly punish the score.
    hard: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Hindi
# --------------------------------------------------------------------------- #
HINDI: list[Case] = [
    Case("बिहार में टमाटर का क्या रेट है?", "hi", "price_query", "Tomato", "Bihar"),
    Case("पटना में गेहूं का भाव क्या है?", "hi", "price_query", "Wheat", "Bihar", "Patna"),
    Case("आलू का दाम बताइए", "hi", "price_query", "Potato"),
    Case("मुजफ्फरपुर में प्याज कितने का है?", "hi", "price_query", "Onion", "Bihar", "Muzaffarpur"),
    Case("चना का मूल्य क्या चल रहा है", "hi", "price_query", "Bengal Gram (Gram)(Whole)"),
    Case("सरसों का रेट गया में", "hi", "price_query", "Mustard", "Bihar", "Gaya"),
    Case("मक्का का भाव", "hi", "price_query", "Maize"),
    Case("लहसुन का दाम आज", "hi", "price_query", "Garlic"),
    Case("आसपास गेहूं कौन खरीद रहा है?", "hi", "buyer_search", "Wheat"),
    Case("पटना में आलू का खरीदार कौन है", "hi", "buyer_search", "Potato", "Bihar", "Patna"),
    Case("टमाटर खरीदने वाले व्यापारी बताइए", "hi", "buyer_search", "Tomato"),
    Case("भागलपुर में चावल कौन खरीदता है", "hi", "buyer_search", "Rice", "Bihar", "Bhagalpur"),
    Case("मंडी का संपर्क नंबर चाहिए", "hi", "buyer_search"),
    Case("क्या मुझे अभी प्याज बेच देना चाहिए?", "hi", "sell_advice", "Onion"),
    Case("गेहूं बेचूं या रुकूं?", "hi", "sell_advice", "Wheat"),
    Case("आलू बेचने का सही समय है क्या", "hi", "sell_advice", "Potato"),
    Case("अभी टमाटर बेचना ठीक रहेगा?", "hi", "sell_advice", "Tomato"),
    Case("मसूर बेच दूं क्या सलाह है", "hi", "sell_advice", "Lentil (Masur)(Whole)"),
    Case("पिछले हफ्ते से आलू का भाव बढ़ा है?", "hi", "trend_analysis", "Potato"),
    Case("प्याज का रुझान क्या है", "hi", "trend_analysis", "Onion"),
    Case("गेहूं का भाव घटा है क्या", "hi", "trend_analysis", "Wheat"),
    Case("टमाटर में तेजी है या मंदी", "hi", "trend_analysis", "Tomato"),
    Case("पिछले महीने चावल का भाव कैसा रहा", "hi", "trend_analysis", "Rice"),
    Case("800001 में गेहूं का भाव", "hi", "price_query", "Wheat", "Bihar", "Patna",
         tags=("pincode",)),
    Case("20 क्विंटल गेहूं का भाव पटना में", "hi", "price_query", "Wheat", "Bihar", "Patna",
         tags=("quantity",)),
]

# --------------------------------------------------------------------------- #
# English
# --------------------------------------------------------------------------- #
ENGLISH: list[Case] = [
    Case("What is the tomato price in Bihar?", "en", "price_query", "Tomato", "Bihar"),
    Case("wheat rate in Patna", "en", "price_query", "Wheat", "Bihar", "Patna"),
    Case("How much does onion cost today", "en", "price_query", "Onion"),
    Case("potato price in Gaya", "en", "price_query", "Potato", "Bihar", "Gaya"),
    Case("current rate of mustard", "en", "price_query", "Mustard"),
    Case("price of green chilli", "en", "price_query", "Green Chilli"),
    Case("Who is buying wheat nearby?", "en", "buyer_search", "Wheat"),
    Case("Which traders purchase potatoes in Patna", "en", "buyer_search", "Potato", "Bihar", "Patna"),
    Case("find buyers for my onions", "en", "buyer_search", "Onion"),
    Case("APMC contact in Muzaffarpur", "en", "buyer_search", None, "Bihar", "Muzaffarpur"),
    Case("Should I sell onions now?", "en", "sell_advice", "Onion"),
    Case("sell or wait for wheat", "en", "sell_advice", "Wheat"),
    Case("Is this a good time to sell tomatoes", "en", "sell_advice", "Tomato"),
    Case("should i hold my potato stock", "en", "sell_advice", "Potato"),
    Case("Has potato price risen from last week?", "en", "trend_analysis", "Potato"),
    Case("what is the trend for onion prices", "en", "trend_analysis", "Onion"),
    Case("is wheat falling or rising", "en", "trend_analysis", "Wheat"),
    Case("tomato price forecast for next week", "en", "trend_analysis", "Tomato"),
    Case("How much are tomatoes selling for in Indore?", "en", "price_query", "Tomato",
         "Madhya Pradesh", "Indore", tags=("plural",)),
    Case("lentils rate in Ludhiana", "en", "price_query", "Lentil (Masur)(Whole)", "Punjab",
         "Ludhiana", tags=("plural",)),
]

# --------------------------------------------------------------------------- #
# Bhojpuri
# --------------------------------------------------------------------------- #
BHOJPURI: list[Case] = [
    Case("पियाज के भाव केतना बा?", "bho", "price_query", "Onion"),
    Case("रउआ बताईं कि गेहूँ के दाम का बा", "bho", "price_query", "Wheat"),
    Case("टमाटर के रेट केतना बाटे", "bho", "price_query", "Tomato"),
    Case("आलू के भाव बताईं", "bho", "price_query", "Potato"),
    Case("चाउर के दाम का बा", "bho", "price_query", "Rice"),
    Case("गेहूँ के कवन कीनत बा", "bho", "buyer_search", "Wheat"),
    Case("आसपास पियाज के बेपारी बाड़न", "bho", "buyer_search", "Onion"),
    Case("अभहीं आलू बेचीं कि रुकीं", "bho", "sell_advice", "Potato"),
    Case("टमाटर बेच दीं का सलाह बा", "bho", "sell_advice", "Tomato"),
    Case("पिछला हफ्ता से भाव बढ़ल बा का", "bho", "trend_analysis"),
    Case("मकई के भाव में तेजी बा", "bho", "trend_analysis", "Maize"),
]

# --------------------------------------------------------------------------- #
# Maithili
# --------------------------------------------------------------------------- #
MAITHILI: list[Case] = [
    Case("गहूम के भाव कतेक अछि?", "mai", "price_query", "Wheat"),
    Case("आलू के दाम कतेक छैक", "mai", "price_query", "Potato"),
    Case("अहाँ बताउ जे प्याज के रेट की अछि", "mai", "price_query", "Onion"),
    Case("चाउर के भाव कतेक अछि", "mai", "price_query", "Rice"),
    Case("गहूम के किनैत बला के अछि", "mai", "buyer_search", "Wheat"),
    Case("हमर आलू केओ किनत", "mai", "buyer_search", "Potato"),
    Case("आब बेचब कि रुकब", "mai", "sell_advice"),
    Case("मकै बेचब से नीक रहत", "mai", "sell_advice", "Maize"),
    Case("पछिला सप्ताह सँ भाव बढ़ल अछि", "mai", "trend_analysis"),
]

# --------------------------------------------------------------------------- #
# Marathi
# --------------------------------------------------------------------------- #
MARATHI: list[Case] = [
    Case("कांद्याचा भाव किती आहे?", "mr", "price_query", "Onion", tags=("inflection",)),
    Case("गव्हाचे भाव काय आहेत", "mr", "price_query", "Wheat", tags=("inflection",)),
    Case("टोमॅटोचा दर किती आहे", "mr", "price_query", "Tomato", tags=("inflection",)),
    Case("बटाट्याची किंमत सांगा", "mr", "price_query", "Potato", tags=("inflection",)),
    Case("तांदळाचा भाव काय आहे", "mr", "price_query", "Rice", tags=("inflection",)),
    Case("कांदा कोण खरेदी करत आहे", "mr", "buyer_search", "Onion"),
    Case("गहू खरेदीदार कुठे आहेत", "mr", "buyer_search", "Wheat"),
    Case("मी आता कांदा विकू का थांबू?", "mr", "sell_advice", "Onion"),
    Case("टोमॅटो विक्री करावी का", "mr", "sell_advice", "Tomato"),
    Case("मागील आठवड्यापासून भाव वाढला का", "mr", "trend_analysis"),
    Case("कांद्याचा कल काय आहे", "mr", "trend_analysis", "Onion"),
]

# --------------------------------------------------------------------------- #
# Bengali
# --------------------------------------------------------------------------- #
BENGALI: list[Case] = [
    Case("আজ পেঁয়াজের দাম কত?", "bn", "price_query", "Onion", tags=("inflection",)),
    Case("গমের দর কত", "bn", "price_query", "Wheat", tags=("inflection",)),
    Case("আলুর দাম কত আজ", "bn", "price_query", "Potato", tags=("inflection",)),
    Case("টমেটোর মূল্য কত", "bn", "price_query", "Tomato", tags=("inflection",)),
    Case("কাঁচা লঙ্কার দাম", "bn", "price_query", "Green Chilli"),
    Case("গম কে কিনছে", "bn", "buyer_search", "Wheat"),
    Case("পেঁয়াজের ক্রেতা কোথায়", "bn", "buyer_search", "Onion"),
    Case("এখন কি আলু বিক্রি করব", "bn", "sell_advice", "Potato"),
    Case("গম বিক্রি করা উচিত কি", "bn", "sell_advice", "Wheat"),
    Case("গত সপ্তাহে দাম কি বেড়েছে", "bn", "trend_analysis"),
    Case("পেঁয়াজের দামের প্রবণতা কি", "bn", "trend_analysis", "Onion"),
]

# --------------------------------------------------------------------------- #
# Tamil
# --------------------------------------------------------------------------- #
TAMIL: list[Case] = [
    Case("இன்று வெங்காயம் விலை எவ்வளவு?", "ta", "price_query", "Onion"),
    Case("கோதுமை விலை என்ன", "ta", "price_query", "Wheat"),
    Case("தக்காளியின் விலை எவ்வளவு", "ta", "price_query", "Tomato", tags=("inflection",)),
    Case("உருளைக்கிழங்கு விலை", "ta", "price_query", "Potato"),
    Case("அரிசி ரேட் என்ன", "ta", "price_query", "Rice"),
    Case("கோதுமை யார் வாங்குகிறார்", "ta", "buyer_search", "Wheat"),
    Case("வெங்காயம் வாங்குபவர் யார்", "ta", "buyer_search", "Onion"),
    Case("இப்போது விற்க வேண்டுமா", "ta", "sell_advice"),
    Case("தக்காளி விற்பனை செய்யலாமா", "ta", "sell_advice", "Tomato"),
    Case("கடந்த வாரம் விலை உயர்ந்ததா", "ta", "trend_analysis"),
]

# --------------------------------------------------------------------------- #
# The awkward tail: code-switching, no crop, no location, near-ties
# --------------------------------------------------------------------------- #
TRICKY: list[Case] = [
    Case("Patna में tomato का rate क्या है", "hi", "price_query", "Tomato", "Bihar", "Patna",
         tags=("code-switch",)),
    Case("mera gehu ka bhav kya hai Patna me", "hi", "price_query", "Wheat", "Bihar", "Patna",
         tags=("romanised",)),
    Case("kanda cha bhav kiti aahe", "mr", "price_query", "Onion", tags=("romanised",)),
    Case("Bhagalpur mein onion ka rate", "hi", "price_query", "Onion", "Bihar", "Bhagalpur",
         tags=("code-switch",)),
    Case("What are the rates today?", "en", "price_query", None, tags=("no-crop",)),
    Case("मंडी में क्या भाव चल रहा है", "hi", "price_query", None, tags=("no-crop",)),
    Case("गेहूं का भाव बढ़ रहा है तो बेच दूं?", "hi", "sell_advice", "Wheat",
         hard=True, tags=("intent-overlap",)),
    Case("Is the onion price going up, should I wait?", "en", "sell_advice", "Onion",
         hard=True, tags=("intent-overlap",)),
    Case("आलू का भाव पिछले हफ्ते से क्या है", "hi", "trend_analysis", "Potato",
         hard=True, tags=("intent-overlap",)),
    Case("wheat buyers and current price in Karnal", "en", "buyer_search", "Wheat", "Haryana",
         "Karnal", hard=True, tags=("intent-overlap",)),
    Case("Ludhiana mandi wheat", "en", "price_query", "Wheat", "Punjab", "Ludhiana",
         tags=("terse",)),
    Case("टमाटर", "hi", "price_query", "Tomato", tags=("terse",)),
    Case("462001 potato rate", "en", "price_query", "Potato", "Madhya Pradesh", "Bhopal",
         tags=("pincode",)),
    Case("phool gobhi ka daam", "hi", "price_query", "Cauliflower", tags=("multiword-crop",)),
    Case("hari mirch ka rate Varanasi", "hi", "price_query", "Green Chilli", "Uttar Pradesh",
         "Varanasi", tags=("multiword-crop",)),
]


# --------------------------------------------------------------------------- #
# Locations named in non-Latin, non-Devanagari scripts
#
# This group exists because its absence hid a real bug. Every location case was
# Hindi or English, so nobody noticed that a Bengali or Tamil farmer naming
# their own district was not resolved at all — the query silently fell back to
# the default districts and answered about somewhere else entirely.
# --------------------------------------------------------------------------- #
MULTISCRIPT_LOCATIONS: list[Case] = [
    Case("পাটনায় গমের দাম কত?", "bn", "price_query", "Wheat", "Bihar", "Patna",
         tags=("script-location",)),
    Case("বিহারে পেঁয়াজের দাম", "bn", "price_query", "Onion", "Bihar",
         tags=("script-location",)),
    Case("মুজাফফরপুরে আলুর দর", "bn", "price_query", "Potato", "Bihar", "Muzaffarpur",
         tags=("script-location",)),
    Case("পাটনায় গম কে কিনছে", "bn", "buyer_search", "Wheat", "Bihar", "Patna",
         tags=("script-location",)),
    Case("பாட்னாவில் கோதுமை விலை என்ன?", "ta", "price_query", "Wheat", "Bihar", "Patna",
         tags=("script-location",)),
    Case("பீகாரில் வெங்காயம் விலை", "ta", "price_query", "Onion", "Bihar",
         tags=("script-location",)),
    Case("கயாவில் தக்காளி விலை", "ta", "price_query", "Tomato", "Bihar", "Gaya",
         tags=("script-location",)),
    Case("इंदौर मध्ये कांद्याचा भाव किती आहे", "mr", "price_query", "Onion",
         "Madhya Pradesh", "Indore", tags=("script-location",)),
    Case("नालंदा मध्ये गव्हाचे भाव", "mr", "price_query", "Wheat", "Bihar", "Nalanda",
         tags=("script-location",)),
    Case("पटना में पियाज के भाव केतना बा", "bho", "price_query", "Onion", "Bihar", "Patna",
         tags=("script-location",)),
    Case("दरभंगा मे गहूम के भाव कतेक अछि", "mai", "price_query", "Wheat", "Bihar", "Darbhanga",
         tags=("script-location",)),
    Case("লুধিয়ানায় গমের দাম", "bn", "price_query", "Wheat", "Punjab", "Ludhiana",
         tags=("script-location",)),
]


ALL_CASES: list[Case] = (
    HINDI + ENGLISH + BHOJPURI + MAITHILI + MARATHI + BENGALI + TAMIL + TRICKY
    + MULTISCRIPT_LOCATIONS
)

BY_LANGUAGE: dict[str, list[Case]] = {}
for _case in ALL_CASES:
    BY_LANGUAGE.setdefault(_case.language, []).append(_case)


def summary() -> dict[str, int]:
    intents: dict[str, int] = {}
    for case in ALL_CASES:
        intents[case.intent] = intents.get(case.intent, 0) + 1
    return {
        "total": len(ALL_CASES),
        "languages": len(BY_LANGUAGE),
        "hard": sum(1 for c in ALL_CASES if c.hard),
        "with_crop": sum(1 for c in ALL_CASES if c.crop),
        "with_location": sum(1 for c in ALL_CASES if c.state or c.district),
        **{f"intent_{k}": v for k, v in sorted(intents.items())},
    }

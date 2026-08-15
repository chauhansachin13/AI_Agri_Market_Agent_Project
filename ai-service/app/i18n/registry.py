"""Language registry (Section 6.3, "Regional Language Expansion").

The report ships Hindi and English and identifies the gap plainly: over 60% of
target farmers speak Bhojpuri, Maithili, Bengali, Marathi or Tamil, and an
interface in formal Hindi alone excludes them.

Each language carries everything the pipeline needs to serve it end to end —
the script it is written in, the dialect markers that separate it from its
Devanagari neighbours, crop names as farmers actually say them, intent trigger
words, and answer templates. Adding an eighth language means adding one entry
here; no other module changes.

Bhojpuri, Maithili, Marathi and Hindi all use Devanagari, so script detection
alone cannot separate them. That is what `markers` is for: high-frequency
function words that are diagnostic of one language and rare in the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Unicode block boundaries for the scripts in scope.
SCRIPT_RANGES: dict[str, tuple[str, str]] = {
    "devanagari": ("ऀ", "ॿ"),
    "bengali": ("ঀ", "৿"),
    "tamil": ("஀", "௿"),
    "latin": ("A", "z"),
}


@dataclass(frozen=True)
class LanguageSpec:
    code: str
    name: str            # endonym, shown in the language picker
    english_name: str
    script: str
    speech_tag: str      # BCP-47 tag for Web Speech recognition/synthesis
    markers: tuple[str, ...] = ()
    # Morphological signals as regexes, for languages whose diagnostic feature
    # is an inflection rather than a word. Bhojpuri's imperative ends in -ईं
    # (बेचीं, रुकीं, बताईं); enumerating every verb would be endless, and
    # missing them means a Bhojpuri farmer is silently answered in Hindi.
    marker_patterns: tuple[str, ...] = ()
    crop_names: dict[str, str] = field(default_factory=dict)
    # Irregular stems that suffix-stripping cannot reach. Marathi गहू (wheat)
    # becomes गव्हाचे in the oblique — the stem alternates rather than taking a
    # suffix, so the inflected form has to be listed outright.
    extra_crop_forms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    intent_triggers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    templates: dict[str, str] = field(default_factory=dict)
    # Set when the language has no dedicated answer templates and must borrow
    # another's — a documented, visible fallback rather than a silent one.
    template_fallback: str | None = None


# --------------------------------------------------------------------------- #
# English
# --------------------------------------------------------------------------- #
ENGLISH = LanguageSpec(
    code="en",
    name="English",
    english_name="English",
    script="latin",
    speech_tag="en-IN",
    markers=("what", "the", "price", "is", "how", "should"),
    intent_triggers={
        "price_query": ("price", "rate", "cost", "value"),
        "buyer_search": ("buyer", "buying", "purchase", "trader", "who is buying"),
        "sell_advice": ("should i sell", "sell now", "sell or wait", "hold"),
        "trend_analysis": ("trend", "rising", "falling", "last week", "forecast"),
    },
    templates={
        "price": (
            "{crop} is selling at about Rs {price} per quintal at {market} mandi in "
            "{district}, the best rate near {where} on {date}."
        ),
        "others": "Other nearby mandis: {listed}.",
        "sell": "Our advice is to sell now — {reason} (confidence {confidence} percent).",
        "wait": "Our advice is to wait — {reason} (confidence {confidence} percent).",
        "trend": (
            "The price has been {direction} over the past few weeks "
            "(7-day average Rs {ema7} against 30-day average Rs {ema30})."
        ),
        "forecast": (
            "Our model expects about Rs {value} per quintal in {horizon} days "
            "({change} percent), likely between Rs {lower} and Rs {upper}."
        ),
        "weather": "Weather note: {weather}",
        "buyers": "Buyers you can contact near {where}: {names}.",
        "none": "No mandi price was reported for {crop} near {where} for the latest arrival day.",
        "degraded": (
            "Note: the live government feed was not reachable, so these figures come from "
            "the offline reference dataset and should be confirmed at the mandi."
        ),
        "rising": "rising",
        "falling": "falling",
        "steady": "steady",
    },
)

# --------------------------------------------------------------------------- #
# Hindi
# --------------------------------------------------------------------------- #
HINDI = LanguageSpec(
    code="hi",
    name="हिंदी",
    english_name="Hindi",
    script="devanagari",
    speech_tag="hi-IN",
    markers=("है", "क्या", "कितना", "मुझे", "मेरा", "कौन", "चाहिए", "रहा"),
    crop_names={
        "Tomato": "टमाटर", "Onion": "प्याज", "Wheat": "गेहूं", "Potato": "आलू",
        "Rice": "चावल", "Lentil (Masur)(Whole)": "मसूर", "Maize": "मक्का",
        "Mustard": "सरसों", "Bengal Gram (Gram)(Whole)": "चना", "Sugarcane": "गन्ना",
        "Cauliflower": "फूल गोभी", "Brinjal": "बैंगन", "Garlic": "लहसुन",
        "Green Chilli": "हरी मिर्च", "Soyabean": "सोयाबीन",
    },
    intent_triggers={
        "price_query": ("भाव", "रेट", "कीमत", "दाम", "मूल्य"),
        "buyer_search": ("खरीद", "खरीदार", "व्यापारी", "कौन खरीद"),
        "sell_advice": ("बेच", "बेचना", "बेचूं", "रुकूं", "सलाह"),
        "trend_analysis": ("बढ़ा", "घटा", "रुझान", "पिछले", "तेजी", "मंदी"),
    },
    templates={
        "price": (
            "{where} के पास {market} मंडी में {crop} का भाव लगभग {price} रुपये प्रति "
            "क्विंटल है। यह {date} का सबसे अच्छा रेट है।"
        ),
        "others": "आसपास की दूसरी मंडियाँ: {listed}।",
        "sell": "हमारी सलाह है कि अभी बेच दें। भरोसा {confidence} प्रतिशत।",
        "wait": "हमारी सलाह है कि अभी रुक जाएँ। भरोसा {confidence} प्रतिशत।",
        "trend": (
            "पिछले कुछ हफ़्तों में भाव {direction} (7 दिन का औसत {ema7} रुपये, "
            "30 दिन का औसत {ema30} रुपये)।"
        ),
        "forecast": (
            "हमारे अनुमान से {horizon} दिन में भाव लगभग {value} रुपये प्रति क्विंटल "
            "हो सकता है ({change} प्रतिशत), और यह {lower} से {upper} रुपये के बीच रहने "
            "की संभावना है।"
        ),
        "weather": "मौसम की बात: {weather}",
        "buyers": "{where} के पास खरीदार: {names}।",
        "none": "{where} के पास {crop} का कोई ताज़ा मंडी भाव नहीं मिला।",
        "degraded": (
            "ध्यान दें: सरकारी लाइव आँकड़े अभी नहीं मिल पाए, इसलिए ये भाव संदर्भ डेटा से हैं। "
            "मंडी जाकर एक बार पक्का कर लें।"
        ),
        "rising": "बढ़ रहा है", "falling": "घट रहा है", "steady": "एक जैसा है",
    },
)

# --------------------------------------------------------------------------- #
# Bhojpuri
# --------------------------------------------------------------------------- #
BHOJPURI = LanguageSpec(
    code="bho",
    name="भोजपुरी",
    english_name="Bhojpuri",
    script="devanagari",
    # "बा"/"बाटे" (is), "रउआ" (you), "केतना" (how much) are the classic
    # Bhojpuri copula and pronouns; none of them occur in standard Hindi.
    speech_tag="hi-IN",
    markers=("बा", "बाटे", "बाड़", "रउआ", "केतना", "कवन", "हमनी", "देब", "करीं", "बानी"),
    # The -ईं imperative (बेचीं, रुकीं, बताईं) and the -त बा progressive, both
    # absent from standard Hindi. `\b` is unreliable straight after a Devanagari
    # combining mark, so the word end is asserted explicitly. The negative
    # lookbehind on ह keeps the very common Hindi नहीं / कहीं / यहीं out.
    marker_patterns=(r"(?<!ह)ीं(?=[\s?।,.]|$)", r"त\s+ब[ाइ]"),
    crop_names={
        "Tomato": "टमाटर", "Onion": "पियाज", "Wheat": "गेहूँ", "Potato": "आलू",
        "Rice": "चाउर", "Lentil (Masur)(Whole)": "मसूर", "Maize": "मकई",
        "Mustard": "सरसों", "Bengal Gram (Gram)(Whole)": "चना", "Sugarcane": "ऊख",
        "Cauliflower": "फूल गोभी", "Brinjal": "भंटा", "Garlic": "लहसुन",
        "Green Chilli": "हरियर मिरचाई", "Soyabean": "सोयाबीन",
    },
    intent_triggers={
        "price_query": ("भाव", "रेट", "दाम", "केतना"),
        "buyer_search": ("खरीद", "कीनत", "बेपारी", "कवन कीन"),
        "sell_advice": ("बेच", "बेचीं", "रुकीं", "सलाह"),
        "trend_analysis": ("बढ़ल", "घटल", "पिछला", "तेजी"),
    },
    templates={
        "price": (
            "{where} के लगे {market} मंडी में {crop} के भाव करीब {price} रुपिया प्रति "
            "क्विंटल बा। ई {date} के सबसे बढ़िया रेट बा।"
        ),
        "others": "आसपास के दूसर मंडी: {listed}।",
        "sell": "हमनी के सलाह बा कि अभहीं बेच दीं। भरोसा {confidence} प्रतिशत।",
        "wait": "हमनी के सलाह बा कि अभहीं रुक जाईं। भरोसा {confidence} प्रतिशत।",
        "trend": (
            "पिछला कुछ हफ्ता में भाव {direction} (7 दिन के औसत {ema7} रुपिया, "
            "30 दिन के औसत {ema30} रुपिया)।"
        ),
        "forecast": (
            "हमनी के अनुमान बा कि {horizon} दिन में भाव करीब {value} रुपिया प्रति "
            "क्विंटल हो सकेला ({change} प्रतिशत)।"
        ),
        "weather": "मौसम के बात: {weather}",
        "buyers": "{where} के लगे खरीददार: {names}।",
        "none": "{where} के लगे {crop} के कवनो ताजा भाव ना मिलल।",
        "degraded": (
            "ध्यान दीं: सरकारी लाइव आँकड़ा अभहीं ना मिल पावल, त ई भाव संदर्भ डेटा से बा। "
            "मंडी जाके एक बेर पक्का कर लीं।"
        ),
        "rising": "बढ़त बा", "falling": "घटत बा", "steady": "एके नियर बा",
    },
)

# --------------------------------------------------------------------------- #
# Maithili
# --------------------------------------------------------------------------- #
MAITHILI = LanguageSpec(
    code="mai",
    name="मैथिली",
    english_name="Maithili",
    script="devanagari",
    speech_tag="hi-IN",
    markers=(
        "अछि", "छैक", "कतेक", "अहाँ", "हमर", "कोना", "गेल", "रहल अछि", "भेटल",
        # The -ब verbal form (बेचब "will sell", रुकब "will wait") is distinctly
        # Maithili. These are listed rather than matched by a `-ब$` regex,
        # because common Hindi words end the same way — खराब, जवाब, मतलब —
        # and a broad pattern would misread ordinary Hindi as Maithili.
        "बेचब", "रुकब", "करब", "देब", "कहब", "लेब", "रखब", "बुझब", "जायब", "आयब",
    ),
    marker_patterns=(r"\S+ैत\s+अछि", r"\bक[ऽ]\s",),
    crop_names={
        "Tomato": "टमाटर", "Onion": "प्याज", "Wheat": "गहूम", "Potato": "आलू",
        "Rice": "चाउर", "Lentil (Masur)(Whole)": "मसूर", "Maize": "मकै",
        "Mustard": "सरिसो", "Bengal Gram (Gram)(Whole)": "चना", "Sugarcane": "ऊख",
        "Cauliflower": "फूलगोभी", "Brinjal": "भाँटा", "Garlic": "लहसुन",
        "Green Chilli": "हरिअर मरिचाइ", "Soyabean": "सोयाबीन",
    },
    intent_triggers={
        "price_query": ("भाव", "रेट", "दाम", "कतेक"),
        "buyer_search": ("किनैत", "खरीद", "बेपारी"),
        "sell_advice": ("बेच", "बेचब", "रुकब", "सलाह"),
        "trend_analysis": ("बढ़ल", "घटल", "पछिला"),
    },
    templates={
        "price": (
            "{where} लग {market} मंडी मे {crop} के भाव लगभग {price} टाका प्रति क्विंटल "
            "अछि। ई {date} के सभ सँ नीक रेट अछि।"
        ),
        "others": "आसपास के दोसर मंडी: {listed}।",
        "sell": "हमर सलाह अछि जे आब बेच दिअ। भरोसा {confidence} प्रतिशत।",
        "wait": "हमर सलाह अछि जे आब रुकि जाउ। भरोसा {confidence} प्रतिशत।",
        "trend": (
            "पछिला किछु सप्ताह मे भाव {direction} (7 दिन के औसत {ema7}, "
            "30 दिन के औसत {ema30})।"
        ),
        "forecast": (
            "हमर अनुमान अछि जे {horizon} दिन मे भाव लगभग {value} टाका प्रति क्विंटल "
            "भऽ सकैत अछि ({change} प्रतिशत)।"
        ),
        "weather": "मौसम के बात: {weather}",
        "buyers": "{where} लग किनैत बला: {names}।",
        "none": "{where} लग {crop} के कोनो ताजा भाव नहि भेटल।",
        "degraded": (
            "ध्यान दिअ: सरकारी लाइव आँकड़ा नहि भेटल, तेँ ई भाव संदर्भ डेटा सँ अछि। "
            "मंडी जा कऽ एक बेर पक्का कऽ लिअ।"
        ),
        "rising": "बढ़ि रहल अछि", "falling": "घटि रहल अछि", "steady": "एक्के रंग अछि",
    },
)

# --------------------------------------------------------------------------- #
# Marathi
# --------------------------------------------------------------------------- #
MARATHI = LanguageSpec(
    code="mr",
    name="मराठी",
    english_name="Marathi",
    script="devanagari",
    speech_tag="mr-IN",
    markers=(
        "आहे", "आहेत", "आणि", "मध्ये", "नाही", "किती", "कसा", "मला", "पाहिजे",
        # Imperatives, past tense and the genitive endings that carry most
        # Marathi questions; "आहे" alone misses "किंमत सांगा" and "भाव वाढला का".
        "सांगा", "किंमत", "करावी", "वाढला", "घसरला", "मागील", "आता", "मी",
        "विकू", "थांबू", "विक्री", "खरेदी", "चा भाव", "ची किंमत", "कुठे",
    ),
    crop_names={
        "Tomato": "टोमॅटो", "Onion": "कांदा", "Wheat": "गहू", "Potato": "बटाटा",
        "Rice": "तांदूळ", "Lentil (Masur)(Whole)": "मसूर", "Maize": "मका",
        "Mustard": "मोहरी", "Bengal Gram (Gram)(Whole)": "हरभरा", "Sugarcane": "ऊस",
        "Cauliflower": "फुलकोबी", "Brinjal": "वांगे", "Garlic": "लसूण",
        "Green Chilli": "हिरवी मिरची", "Soyabean": "सोयाबीन",
    },
    extra_crop_forms={
        "Wheat": ("गव्ह", "गव्हा"),      # गहू -> गव्हाचे
        "Rice": ("तांदळा",),             # तांदूळ -> तांदळाचा
        "Brinjal": ("वांग",),
        "Garlic": ("लसणा",),
    },
    intent_triggers={
        "price_query": ("भाव", "दर", "किंमत", "किती"),
        "buyer_search": ("खरेदी", "खरेदीदार", "व्यापारी", "कोण घेत"),
        "sell_advice": ("विकू", "विक्री", "थांबू", "सल्ला"),
        "trend_analysis": ("वाढला", "घसरला", "मागील", "कल"),
    },
    templates={
        # Phrased with a dash rather than "{crop} चा", because Marathi would
        # require the oblique form of the crop name there (कांदा -> कांद्याचा)
        # and the registry stores citation forms.
        "price": (
            "{where} जवळ {market} मंडईत {crop} — भाव अंदाजे {price} रुपये प्रति "
            "क्विंटल आहे. हा {date} चा सर्वोत्तम दर आहे."
        ),
        "others": "जवळच्या इतर मंडया: {listed}.",
        "sell": "आमचा सल्ला आहे की आत्ता विकून टाका. खात्री {confidence} टक्के.",
        "wait": "आमचा सल्ला आहे की आत्ता थांबा. खात्री {confidence} टक्के.",
        "trend": (
            "गेल्या काही आठवड्यांत भाव {direction} (7 दिवसांची सरासरी {ema7} रुपये, "
            "30 दिवसांची सरासरी {ema30} रुपये)."
        ),
        "forecast": (
            "आमच्या अंदाजानुसार {horizon} दिवसांत भाव सुमारे {value} रुपये प्रति "
            "क्विंटल होऊ शकतो ({change} टक्के)."
        ),
        "weather": "हवामानाची नोंद: {weather}",
        "buyers": "{where} जवळचे खरेदीदार: {names}.",
        "none": "{where} जवळ {crop} चा ताजा मंडई भाव मिळाला नाही.",
        "degraded": (
            "लक्षात घ्या: सरकारी थेट आकडेवारी मिळाली नाही, त्यामुळे हे दर संदर्भ "
            "डेटावरून आहेत. मंडईत जाऊन एकदा खात्री करून घ्या."
        ),
        "rising": "वाढत आहे", "falling": "घसरत आहे", "steady": "स्थिर आहे",
    },
)

# --------------------------------------------------------------------------- #
# Bengali
# --------------------------------------------------------------------------- #
BENGALI = LanguageSpec(
    code="bn",
    name="বাংলা",
    english_name="Bengali",
    script="bengali",
    speech_tag="bn-IN",
    markers=("কত", "কি", "আছে", "আমার", "কে", "উচিত", "দাম"),
    crop_names={
        "Tomato": "টমেটো", "Onion": "পেঁয়াজ", "Wheat": "গম", "Potato": "আলু",
        "Rice": "চাল", "Lentil (Masur)(Whole)": "মসুর", "Maize": "ভুট্টা",
        "Mustard": "সরিষা", "Bengal Gram (Gram)(Whole)": "ছোলা", "Sugarcane": "আখ",
        "Cauliflower": "ফুলকপি", "Brinjal": "বেগুন", "Garlic": "রসুন",
        "Green Chilli": "কাঁচা লঙ্কা", "Soyabean": "সয়াবিন",
    },
    intent_triggers={
        "price_query": ("দাম", "দর", "মূল্য", "কত"),
        "buyer_search": ("ক্রেতা", "কিনছে", "ব্যবসায়ী"),
        "sell_advice": ("বিক্রি", "বেচব", "অপেক্ষা", "পরামর্শ"),
        "trend_analysis": ("বেড়েছে", "কমেছে", "গত সপ্তাহে", "প্রবণতা"),
    },
    templates={
        "price": (
            "{where} এর কাছে {market} মান্ডিতে {crop} এর দাম প্রায় {price} টাকা প্রতি "
            "কুইন্টাল। এটি {date} তারিখের সেরা দর।"
        ),
        "others": "কাছাকাছি অন্যান্য মান্ডি: {listed}।",
        "sell": "আমাদের পরামর্শ এখনই বিক্রি করে দিন। আস্থা {confidence} শতাংশ।",
        "wait": "আমাদের পরামর্শ এখন অপেক্ষা করুন। আস্থা {confidence} শতাংশ।",
        "trend": (
            "গত কয়েক সপ্তাহে দাম {direction} (৭ দিনের গড় {ema7} টাকা, "
            "৩০ দিনের গড় {ema30} টাকা)।"
        ),
        "forecast": (
            "আমাদের অনুমান অনুযায়ী {horizon} দিনে দাম প্রায় {value} টাকা প্রতি "
            "কুইন্টাল হতে পারে ({change} শতাংশ)।"
        ),
        "weather": "আবহাওয়ার কথা: {weather}",
        "buyers": "{where} এর কাছে ক্রেতা: {names}।",
        "none": "{where} এর কাছে {crop} এর কোনো সাম্প্রতিক দাম পাওয়া যায়নি।",
        "degraded": (
            "লক্ষ্য করুন: সরকারি সরাসরি তথ্য পাওয়া যায়নি, তাই এই দরগুলি রেফারেন্স "
            "ডেটা থেকে। মান্ডিতে গিয়ে একবার যাচাই করে নিন।"
        ),
        "rising": "বাড়ছে", "falling": "কমছে", "steady": "একই রকম",
    },
)

# --------------------------------------------------------------------------- #
# Tamil
# --------------------------------------------------------------------------- #
TAMIL = LanguageSpec(
    code="ta",
    name="தமிழ்",
    english_name="Tamil",
    script="tamil",
    speech_tag="ta-IN",
    markers=("என்ன", "எவ்வளவு", "விலை", "நான்", "யார்", "வேண்டும்"),
    crop_names={
        "Tomato": "தக்காளி", "Onion": "வெங்காயம்", "Wheat": "கோதுமை", "Potato": "உருளைக்கிழங்கு",
        "Rice": "அரிசி", "Lentil (Masur)(Whole)": "மைசூர் பருப்பு", "Maize": "மக்காச்சோளம்",
        "Mustard": "கடுகு", "Bengal Gram (Gram)(Whole)": "கொண்டைக்கடலை", "Sugarcane": "கரும்பு",
        "Cauliflower": "காலிஃபிளவர்", "Brinjal": "கத்தரிக்காய்", "Garlic": "பூண்டு",
        "Green Chilli": "பச்சை மிளகாய்", "Soyabean": "சோயாபீன்",
    },
    intent_triggers={
        "price_query": ("விலை", "ரேட்", "எவ்வளவு"),
        "buyer_search": ("வாங்குபவர்", "வாங்குகிறார்", "வியாபாரி"),
        "sell_advice": ("விற்க", "விற்பனை", "காத்திரு", "ஆலோசனை"),
        "trend_analysis": ("உயர்ந்த", "குறைந்த", "கடந்த வாரம்", "போக்கு"),
    },
    templates={
        "price": (
            "{where} அருகே {market} மண்டியில் {crop} விலை ஒரு குவிண்டாலுக்கு சுமார் "
            "{price} ரூபாய். இது {date} அன்றைய சிறந்த விலை."
        ),
        "others": "அருகிலுள்ள மற்ற மண்டிகள்: {listed}.",
        "sell": "எங்கள் ஆலோசனை: இப்போதே விற்றுவிடுங்கள். நம்பிக்கை {confidence} சதவீதம்.",
        "wait": "எங்கள் ஆலோசனை: இப்போது காத்திருங்கள். நம்பிக்கை {confidence} சதவீதம்.",
        "trend": (
            "கடந்த சில வாரங்களில் விலை {direction} (7 நாள் சராசரி {ema7} ரூபாய், "
            "30 நாள் சராசரி {ema30} ரூபாய்)."
        ),
        "forecast": (
            "எங்கள் மதிப்பீட்டின்படி {horizon} நாட்களில் விலை சுமார் {value} ரூபாய் "
            "ஆகலாம் ({change} சதவீதம்)."
        ),
        "weather": "வானிலை குறிப்பு: {weather}",
        "buyers": "{where} அருகே வாங்குபவர்கள்: {names}.",
        "none": "{where} அருகே {crop} விலை எதுவும் கிடைக்கவில்லை.",
        "degraded": (
            "கவனிக்கவும்: அரசு நேரடி தரவு கிடைக்கவில்லை, எனவே இந்த விலைகள் குறிப்பு "
            "தரவிலிருந்து. மண்டிக்குச் சென்று ஒருமுறை உறுதி செய்யுங்கள்."
        ),
        "rising": "உயர்ந்து வருகிறது", "falling": "குறைந்து வருகிறது", "steady": "நிலையாக உள்ளது",
    },
)


LANGUAGES: dict[str, LanguageSpec] = {
    spec.code: spec
    for spec in (ENGLISH, HINDI, BHOJPURI, MAITHILI, MARATHI, BENGALI, TAMIL)
}

SUPPORTED_CODES = tuple(LANGUAGES)
DEFAULT_CODE = "hi"

# Languages sharing Devanagari, checked against each other by marker frequency.
DEVANAGARI_LANGUAGES = tuple(
    code for code, spec in LANGUAGES.items() if spec.script == "devanagari"
)


def get_language(code: str | None) -> LanguageSpec:
    """Return a language spec, falling back to Hindi for anything unknown."""
    if not code:
        return LANGUAGES[DEFAULT_CODE]
    return LANGUAGES.get(code, LANGUAGES[DEFAULT_CODE])


def template(code: str, key: str) -> str:
    """A template string, following the declared fallback chain if needed."""
    spec = get_language(code)
    if key in spec.templates:
        return spec.templates[key]
    if spec.template_fallback:
        return template(spec.template_fallback, key)
    return LANGUAGES[DEFAULT_CODE].templates.get(key, "")


def crop_label(code: str, commodity: str | None) -> str:
    """Crop name in the requested language, falling back to the English name."""
    if not commodity:
        return get_language(code).crop_names.get("__generic__", "crop")
    spec = get_language(code)
    return spec.crop_names.get(commodity, commodity)

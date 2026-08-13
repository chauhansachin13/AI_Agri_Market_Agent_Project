# Regional languages

The report ships Hindi and English and states the gap directly: over 60% of
target farmers speak Bhojpuri, Maithili, Bengali, Marathi or Tamil, and an
interface in formal Hindi alone excludes them. Section 6.3 asks for that
expansion.

## Supported languages

| Code | Language | Script | Speech tag |
|---|---|---|---|
| `en` | English | Latin | `en-IN` |
| `hi` | हिंदी | Devanagari | `hi-IN` |
| `bho` | भोजपुरी | Devanagari | `hi-IN` ¹ |
| `mai` | मैथिली | Devanagari | `hi-IN` ¹ |
| `mr` | मराठी | Devanagari | `mr-IN` |
| `bn` | বাংলা | Bengali | `bn-IN` |
| `ta` | தமிழ் | Tamil | `ta-IN` |

¹ No browser recogniser exists for Bhojpuri or Maithili, so they borrow Hindi.
This is imperfect — Section 6.2 already records that Hindi recognition degrades
on these accents — and it is better than having no voice input at all. The
typed path is never taken away.

## Adding a language

Add one `LanguageSpec` to `app/i18n/registry.py`. No other module changes.

```python
GUJARATI = LanguageSpec(
    code="gu",
    name="ગુજરાતી",
    english_name="Gujarati",
    script="gujarati",
    speech_tag="gu-IN",
    markers=("કેટલું", "છે", "ભાવ"),
    crop_names={"Tomato": "ટામેટા", "Onion": "ડુંગળી", ...},
    intent_triggers={"price_query": ("ભાવ", "કિંમત"), ...},
    templates={"price": "...", "sell": "...", ...},
)
```

A test enforces that every registered language can fill every template slot, so
a half-finished entry fails the suite rather than silently emitting empty
sentences.

## Detection

Two stages, in order.

**1. Script.** Bengali and Tamil own their Unicode blocks, so a query in either
is settled immediately.

Presence of an Indic script decides the language even when Latin characters
outnumber it. Romanised place names and English loanwords are long — *"Patna
में tomato का rate क्या है"* is majority-Latin by character count — and
answering that in English is exactly the exclusion this system exists to remove.

**2. Markers.** Hindi, Bhojpuri, Maithili and Marathi all use Devanagari, so
script cannot separate them. Diagnostic function words decide: `बा` is
Bhojpuri, `अछि` is Maithili, `आहे` is Marathi, and none appears in standard
Hindi. Hindi wins ties, being both the most common input and the safest
fallback for the group.

### Morphology, and two traps in it

Some of the strongest signals are inflections rather than words.

**Bhojpuri's `-ईं` imperative** (बेचीं, रुकीं, बताईं) is matched by regex —
enumerating every verb would be endless. But `नहीं`, `कहीं` and `यहीं` are
extremely common Hindi words with the same ending, so the pattern carries a
negative lookbehind on `ह`. Python's `\b` is also unreliable straight after a
Devanagari combining mark, so the word end is asserted explicitly.

**Maithili's `-ब` verbal** (बेचब "will sell", रुकब "will wait") is the opposite
case: here the regex is the trap. `खराब`, `जवाब` and `मतलब` are ordinary Hindi
words ending in `-ब`, and `खराब` in particular is very likely in a crop query.
So the verb forms are enumerated instead.

Both traps have regression tests.

## Crop extraction and Indic inflection

Indic languages inflect by replacing the final vowel sign, not by appending to
it. Marathi कांदा (onion) appears as कांद्याचा in the oblique, so the citation
form is not even a prefix of the inflected one, and plain containment misses it.

Two mechanisms handle this:

1. **Stem matching** — trailing vowel signs are stripped, so कांद matches
   कांद्याचा, and Bengali পেঁয়াজ matches পেঁয়াজের.
2. **Irregular forms** — where the stem itself alternates (Marathi गहू → गव्ह,
   तांदूळ → तांदळा), the inflected stem is listed outright in
   `extra_crop_forms`.

English plurals are handled separately, including the `-oes` cases: farmers
write "tomatoes" and "onions", and the lexicon stores singulars.

## Answer generation

Answers are assembled from per-language templates whose slots hold only numbers
and proper nouns. **Nothing that matters is machine-translated.** A
mistranslated sentence containing "₹2,714 per quintal" is a real risk to a
farmer, and the template path removes it by construction.

NLLB-200 is used only for free text with no template — an LLM-written answer,
for instance — and only when `transformers` is installed. Otherwise the text is
returned untranslated and marked as such, which is better than emitting a
mangled price.

Three languages are always produced: the farmer's own, plus English and Hindi,
so `english_answer` and `hindi_answer` stay populated for clients written
against the report's Section 4.7 schema even when the farmer wrote in Tamil.

## Place names

State and district names render in Devanagari for `hi`, `bho`, `mai` and `mr`
where a known form exists. **Mandi names are never transliterated** — a farmer
looks for the name painted on the yard gate, which is the one Agmarknet
publishes.

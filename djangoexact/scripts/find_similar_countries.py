"""
Script to find duplicate or similar country names in the database.

Uses multiple matching strategies:
- Exact match (case-insensitive, normalized)
- Parenthetical variation detection
- Prefix/starts-with matching
- Phonetic matching (Soundex)
- Token-based matching
- Comprehensive semantic aliases database (historical names, alternative names, etc.)

Usage: python manage.py runscript find_similar_countries
       python manage.py runscript find_similar_countries --script-args="--threshold=0.4"
"""

import re
import unicodedata
from difflib import SequenceMatcher
from itertools import combinations

from api.models import Country


# Common words to ignore when comparing core names
STRIP_WORDS = {
    "the",
    "of",
    "and",
    "republic",
    "democratic",
    "peoples",
    "people's",
    "kingdom",
    "state",
    "states",
    "united",
    "federation",
    "federated",
    "islands",
    "island",
    "special",
    "administrative",
    "region",
    "territory",
    "territories",
    "autonomous",
    "province",
    "part",
    "arab",
    "islamic",
    "plurinational",
    "bolivarian",
    "socialist",
    "popular",
    "great",
    "northern",
}

# Comprehensive semantic aliases - countries with multiple names
# Format: canonical name -> list of alternative names/spellings
SEMANTIC_ALIASES = {
    # Taiwan / Chinese Taipei variations
    "taiwan": ["chinese taipei", "taipei", "republic of china", "roc", "formosa"],
    # Korea variations
    "north korea": ["democratic peoples republic of korea", "dprk", "korea north", "pyongyang"],
    "south korea": ["republic of korea", "korea south", "rok"],
    # China variations
    "china": ["peoples republic of china", "prc", "mainland china"],
    "hong kong": ["hong kong sar", "china hong kong", "hk", "hongkong"],
    "macao": ["macau", "macao sar", "china macao"],
    # Congo variations
    "congo republic": ["congo", "congo brazzaville", "republic of congo", "republic of the congo"],
    "congo drc": ["democratic republic of congo", "democratic republic of the congo", "drc", "dr congo", "congo kinshasa", "zaire"],
    # Name changes / historical names
    "myanmar": ["burma"],
    "eswatini": ["swaziland"],
    "sri lanka": ["ceylon"],
    "thailand": ["siam"],
    "iran": ["persia", "iran islamic republic"],
    "iraq": ["mesopotamia"],
    "zimbabwe": ["rhodesia", "southern rhodesia"],
    "zambia": ["northern rhodesia"],
    "malawi": ["nyasaland"],
    "botswana": ["bechuanaland"],
    "lesotho": ["basutoland"],
    "ghana": ["gold coast"],
    "benin": ["dahomey"],
    "burkina faso": ["upper volta"],
    "cambodia": ["kampuchea"],
    "bangladesh": ["east pakistan"],
    "namibia": ["south west africa"],
    "ethiopia": ["abyssinia"],
    "jordan": ["transjordan"],
    "saudi arabia": ["hejaz", "nejd"],
    "turkey": ["turkiye", "ottoman"],
    "russia": ["russian federation", "ussr", "soviet union"],
    "north macedonia": ["macedonia", "fyrom", "former yugoslav republic of macedonia"],
    # European variations
    "czechia": ["czech republic", "czechoslovakia"],
    "slovakia": ["czechoslovakia"],
    "netherlands": ["holland"],
    "uk": ["united kingdom", "great britain", "britain", "england", "united kingdom of great britain"],
    "ireland": ["eire", "republic of ireland"],
    "germany": ["west germany", "east germany", "federal republic of germany"],
    "belgium": ["flanders", "wallonia"],
    "switzerland": ["helvetia", "swiss confederation"],
    "vatican": ["vatican city", "holy see"],
    "monaco": ["monte carlo"],
    # Americas variations
    "usa": ["united states", "united states of america", "us", "america"],
    "bolivia": ["bolivia plurinational state", "plurinational state of bolivia"],
    "venezuela": ["venezuela bolivarian republic", "bolivarian republic of venezuela"],
    # African variations
    "ivory coast": ["cote divoire", "côte d'ivoire", "cote d ivoire"],
    "cabo verde": ["cape verde"],
    "reunion": ["réunion"],
    # Asian variations
    "vietnam": ["viet nam"],
    "laos": ["lao", "lao pdr", "lao peoples democratic republic"],
    "brunei": ["brunei darussalam"],
    "timor leste": ["east timor", "timor-leste"],
    "philippines": ["philippine islands"],
    # Pacific variations
    "micronesia": ["federated states of micronesia", "fsm"],
    "papua new guinea": ["png"],
    # Caribbean / Atlantic
    "saint martin": ["sint maarten", "st martin", "st maarten", "san martin"],
    "saint kitts": ["st kitts", "saint christopher"],
    "saint lucia": ["st lucia"],
    "saint vincent": ["st vincent"],
    "saint helena": ["st helena"],
    "falkland islands": ["malvinas", "falklands"],
    "curacao": ["curaçao"],
    # Middle East
    "syria": ["syrian arab republic"],
    "palestine": ["palestinian territory", "state of palestine", "west bank", "gaza"],
    "uae": ["united arab emirates", "emirates"],
    # Central Asia
    "kyrgyzstan": ["kirghizia", "kyrgyz republic"],
    "tajikistan": ["tadzhikistan"],
    "turkmenistan": ["turkmenia"],
    # Moldova / Tanzania
    "moldova": ["moldavia", "republic of moldova"],
    "tanzania": ["tanganyika", "zanzibar", "united republic of tanzania"],
}


def normalize_string(s: str) -> str:
    """Normalize: lowercase, remove diacritics, punctuation, BOM, extra whitespace."""
    s = s.lower()
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\xa0", " ")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", " ", s)
    s = " ".join(s.split())
    return s


def remove_parenthetical(s: str) -> str:
    """Remove parenthetical content from string."""
    result = re.sub(r"\s*\([^)]*\)", "", s)
    return result.strip()


def get_base_name(s: str) -> str:
    """Get base name without parenthetical additions, normalized."""
    return normalize_string(remove_parenthetical(s))


def get_core_name(s: str) -> str:
    """Extract core name by removing common descriptive words."""
    normalized = normalize_string(s)
    words = normalized.split()
    core_words = [w for w in words if w not in STRIP_WORDS]
    return " ".join(core_words) if core_words else normalized


def get_first_word(s: str) -> str:
    """Get the first significant word."""
    words = [w for w in normalize_string(s).split() if w not in STRIP_WORDS and len(w) > 2]
    return words[0] if words else ""


def get_significant_words(s: str) -> set:
    """Get set of significant words (excluding common words)."""
    words = normalize_string(s).split()
    return {w for w in words if w not in STRIP_WORDS and len(w) > 2}


def soundex(name: str) -> str:
    """Generate Soundex code."""
    name = normalize_string(name).replace(" ", "")
    if not name:
        return ""
    codes = {"b": "1", "f": "1", "p": "1", "v": "1", "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2", "d": "3", "t": "3", "l": "4", "m": "5", "n": "5", "r": "6"}
    first_letter = name[0].upper()
    coded = first_letter
    prev_code = codes.get(name[0], "")
    for char in name[1:]:
        code = codes.get(char, "")
        if code and code != prev_code:
            coded += code
        prev_code = code if code else prev_code
    return (coded + "000")[:4]


def get_ngrams(s: str, n: int = 2) -> set:
    """Get character n-grams."""
    s = normalize_string(s).replace(" ", "")
    if len(s) < n:
        return {s}
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def ngram_similarity(name1: str, name2: str, n: int = 2) -> float:
    """Calculate Jaccard similarity between n-gram sets."""
    ngrams1 = get_ngrams(name1, n)
    ngrams2 = get_ngrams(name2, n)
    if not ngrams1 or not ngrams2:
        return 0.0
    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2
    return len(intersection) / len(union)


def check_semantic_alias(name1: str, name2: str) -> tuple[bool, str]:
    """
    Check if two names are semantic aliases (same country, different names).
    Returns (is_alias, alias_group_name).
    """
    n1 = normalize_string(name1)
    n2 = normalize_string(name2)
    b1 = get_base_name(name1)
    b2 = get_base_name(name2)

    # Extract content inside parentheses for additional matching
    def get_parenthetical(s):
        match = re.search(r"\(([^)]+)\)", s)
        return normalize_string(match.group(1)) if match else ""

    p1 = get_parenthetical(name1)
    p2 = get_parenthetical(name2)

    for canonical, aliases in SEMANTIC_ALIASES.items():
        all_forms = [normalize_string(canonical)] + [normalize_string(a) for a in aliases]

        def matches_group(name, base, paren):
            # Exact match with any form
            if name in all_forms or base in all_forms:
                return True
            # Parenthetical content matches
            if paren and paren in all_forms:
                return True
            # Check if name STARTS with any alias
            for form in all_forms:
                if len(form) >= 4:
                    if name.startswith(form + " ") or name.startswith(form + ",") or name.startswith(form + "("):
                        return True
                    if base == form:
                        return True
                    # Check if form appears as a complete word in the name
                    if f" {form} " in f" {name} " or f" {form}," in f" {name},":
                        return True
            return False

        n1_matches = matches_group(n1, b1, p1)
        n2_matches = matches_group(n2, b2, p2)

        if n1_matches and n2_matches and n1 != n2:
            return True, canonical

    return False, ""


def is_parenthetical_variant(name1: str, name2: str) -> bool:
    """Check if one name is a parenthetical variant of the other."""
    base1 = get_base_name(name1)
    base2 = get_base_name(name2)
    norm1 = normalize_string(name1)
    norm2 = normalize_string(name2)

    if base1 == base2 and norm1 != norm2 and len(base1) >= 4:
        return True

    return False


def is_prefix_variant(name1: str, name2: str) -> bool:
    """Check if one name starts with the other (prefix variant)."""
    n1 = normalize_string(name1)
    n2 = normalize_string(name2)

    if n1.startswith(n2) or n2.startswith(n1):
        shorter = min(len(n1), len(n2))
        if shorter >= 4:
            return True

    b1 = get_base_name(name1)
    b2 = get_base_name(name2)
    if b1 and b2 and len(min(b1, b2, key=len)) >= 4:
        if b1.startswith(b2) or b2.startswith(b1):
            return True

    return False


def word_overlap_ratio(name1: str, name2: str) -> float:
    """Calculate the ratio of overlapping significant words."""
    words1 = get_significant_words(name1)
    words2 = get_significant_words(name2)

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def calculate_similarity(name1: str, name2: str) -> dict:
    """Calculate multiple similarity metrics."""
    norm1 = normalize_string(name1)
    norm2 = normalize_string(name2)
    base1 = get_base_name(name1)
    base2 = get_base_name(name2)
    core1 = get_core_name(name1)
    core2 = get_core_name(name2)

    is_alias, alias_group = check_semantic_alias(name1, name2)

    return {
        "normalized_match": norm1 == norm2,
        "base_name_match": base1 == base2 and len(base1) >= 4,
        "core_name_match": core1 == core2 and len(core1) >= 3,
        "parenthetical_variant": is_parenthetical_variant(name1, name2),
        "prefix_variant": is_prefix_variant(name1, name2),
        "semantic_alias": is_alias,
        "alias_group": alias_group,
        "first_word_match": get_first_word(name1) == get_first_word(name2) and len(get_first_word(name1)) >= 4,
        "soundex_match": soundex(name1) == soundex(name2),
        "word_overlap": word_overlap_ratio(name1, name2),
        "sequence_ratio": SequenceMatcher(None, norm1, norm2).ratio(),
        "ngram_similarity": ngram_similarity(name1, name2),
    }


def compute_score(metrics: dict) -> tuple[float, str]:
    """Compute combined score and primary reason."""
    # Definite matches
    if metrics["normalized_match"]:
        return 1.0, "EXACT MATCH (after normalization)"

    if metrics["base_name_match"] and metrics["parenthetical_variant"]:
        return 0.98, "SAME BASE NAME with parenthetical variation"

    if metrics["semantic_alias"]:
        return 0.95, f"SEMANTIC ALIAS (same as '{metrics['alias_group']}')"

    if metrics["parenthetical_variant"]:
        return 0.90, "PARENTHETICAL VARIANT"

    # High confidence
    if metrics["prefix_variant"] and metrics["first_word_match"]:
        return 0.85, "PREFIX VARIANT (same start)"

    if metrics["core_name_match"] and metrics["first_word_match"]:
        return 0.80, "SAME CORE NAME"

    # Medium confidence
    if metrics["prefix_variant"] and metrics["soundex_match"]:
        return 0.75, "PREFIX + PHONETIC MATCH"

    if metrics["first_word_match"] and metrics["soundex_match"]:
        return 0.70, "FIRST WORD + PHONETIC MATCH"

    if metrics["word_overlap"] >= 0.5 and metrics["first_word_match"]:
        return 0.65, "SIGNIFICANT WORD OVERLAP"

    # Lower confidence - weighted average
    score = metrics["sequence_ratio"] * 0.35 + metrics["ngram_similarity"] * 0.25 + metrics["word_overlap"] * 0.20 + (0.10 if metrics["first_word_match"] else 0) + (0.10 if metrics["soundex_match"] else 0)

    return score, "SIMILARITY SCORE"


def find_similar_countries(countries: list[Country], threshold: float = 0.4) -> list[dict]:
    """Find pairs of countries with similar names."""
    results = []

    for c1, c2 in combinations(countries, 2):
        metrics = calculate_similarity(c1.name, c2.name)
        score, reason = compute_score(metrics)

        if score >= threshold:
            results.append(
                {
                    "country1": c1,
                    "country2": c2,
                    "score": score,
                    "reason": reason,
                    "metrics": metrics,
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def find_self_referencing_aliases(countries: list[Country]) -> list[dict]:
    """
    Find entries where the parenthetical content is an alias of the base name.
    E.g., "Taiwan (Chinese Taipei)" - both names refer to same place.
    """
    results = []

    for country in countries:
        match = re.search(r"^(.+?)\s*\((.+)\)$", country.name)
        if not match:
            continue

        base = normalize_string(match.group(1).strip())
        paren = normalize_string(match.group(2).strip())

        if not base or not paren or base == paren:
            continue

        # Check if base and paren are in the same alias group
        for canonical, aliases in SEMANTIC_ALIASES.items():
            all_forms = [normalize_string(canonical)] + [normalize_string(a) for a in aliases]

            base_matches = base in all_forms or any(base == f for f in all_forms)
            paren_matches = paren in all_forms or any(paren == f for f in all_forms)

            if base_matches and paren_matches:
                results.append(
                    {
                        "country": country,
                        "base": match.group(1).strip(),
                        "paren": match.group(2).strip(),
                        "alias_group": canonical,
                    }
                )
                break

    return results


def run(*args):
    """Main function called by runscript."""
    threshold = 0.4
    for arg in args:
        if arg.startswith("--threshold="):
            try:
                threshold = float(arg.split("=")[1])
            except ValueError:
                print(f"Invalid threshold: {arg}")
                return

    print("Fetching all countries...")
    countries = list(Country.objects.all())
    print(f"Found {len(countries)} countries")
    print(f"Threshold: {threshold:.0%}\n")

    # First, find self-referencing aliases (single entries with redundant names)
    self_refs = find_self_referencing_aliases(countries)
    if self_refs:
        print("=" * 80)
        print("SELF-REFERENCING ALIASES (single entry with redundant naming)")
        print("=" * 80)
        for r in self_refs:
            c = r["country"]
            print(f"\nID {c.pk}: '{c.name}'")
            print(f"  Base name: '{r['base']}' | Parenthetical: '{r['paren']}'")
            print(f"  Both are aliases for: '{r['alias_group']}'")
        print()

    results = find_similar_countries(countries, threshold)

    # Group results
    definite = [r for r in results if r["score"] >= 0.95]
    high = [r for r in results if 0.75 <= r["score"] < 0.95]
    medium = [r for r in results if 0.50 <= r["score"] < 0.75]
    low = [r for r in results if r["score"] < 0.50]

    # DEFINITE
    print("=" * 80)
    print("DEFINITE DUPLICATES (>= 95%)")
    print("=" * 80)
    if definite:
        for r in definite:
            c1, c2 = r["country1"], r["country2"]
            print(f"\n[{r['score']:.0%}] {r['reason']}")
            print(f"  1) ID {c1.pk:>4}: '{c1.name}'")
            print(f"  2) ID {c2.pk:>4}: '{c2.name}'")
    else:
        print("None found.")

    # HIGH
    print("\n" + "=" * 80)
    print("HIGH CONFIDENCE (75-94%)")
    print("=" * 80)
    if high:
        for r in high:
            c1, c2 = r["country1"], r["country2"]
            print(f"\n[{r['score']:.0%}] {r['reason']}")
            print(f"  1) ID {c1.pk:>4}: '{c1.name}'")
            print(f"  2) ID {c2.pk:>4}: '{c2.name}'")
    else:
        print("None found.")

    # MEDIUM
    print("\n" + "=" * 80)
    print("MEDIUM CONFIDENCE (50-74%)")
    print("=" * 80)
    if medium:
        for r in medium:
            c1, c2 = r["country1"], r["country2"]
            print(f"\n[{r['score']:.0%}] {r['reason']}")
            print(f"  1) ID {c1.pk:>4}: '{c1.name}'")
            print(f"  2) ID {c2.pk:>4}: '{c2.name}'")
    else:
        print("None found.")

    # LOW (summary only)
    print("\n" + "=" * 80)
    print(f"LOW CONFIDENCE ({threshold:.0%}-49%): {len(low)} matches")
    print("=" * 80)
    if low:
        for r in low:
            print(f"[{r['score']:.0%}] '{r['country1'].name}' <-> '{r['country2'].name}'")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Countries analyzed: {len(countries)}")
    print(f"Definite duplicates: {len(definite)}")
    print(f"High confidence: {len(high)}")
    print(f"Medium confidence: {len(medium)}")
    print(f"Low confidence: {len(low)}")

    if definite or high:
        print("\n" + "=" * 80)
        print("IDs TO REVIEW")
        print("=" * 80)
        ids = set()
        for r in definite + high:
            ids.add(r["country1"].pk)
            ids.add(r["country2"].pk)
        print(f"IDs: {sorted(ids)}")

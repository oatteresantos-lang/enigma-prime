"""
ENIGMA PRIME - Brique 2 : Extraction des patterns viraux
==========================================================

Ce script lit le fichier généré par la Brique 1 (viral_horror_data.json)
et en extrait des patterns concrets et réutilisables :

1. Durée optimale (en croisant durée vidéo <-> nombre de vues)
2. Mots-clés / structures qui reviennent dans les titres les plus performants
3. Structure narrative type (en découpant les transcripts en 3 parties :
   introduction / développement / chute, et en observant leur longueur relative)
4. Un "brief" condensé, prêt à être injecté dans le prompt de génération
   IA de la Brique 3

Prérequis :
    pip install isodate --break-system-packages

Usage :
    python extract_patterns.py
    (le fichier viral_horror_data.json doit être dans le même dossier)
"""

import json
import re
from collections import Counter

import isodate

INPUT_FILE = "viral_horror_data.json"
OUTPUT_FILE = "patterns_brief.json"

# Mots vides à ignorer dans l'analyse des titres (français)
STOPWORDS = {
    "de", "la", "le", "les", "un", "une", "des", "du", "et", "à", "au", "aux",
    "en", "sur", "dans", "pour", "par", "ce", "cette", "ces", "qui", "que",
    "qu", "se", "sa", "son", "ses", "ne", "pas", "plus", "est", "sont",
    "avec", "sans", "il", "elle", "on", "je", "tu", "nous", "vous", "ils",
    "elles", "j", "l", "d", "s", "c", "n", "m", "y", "a",
}


def load_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_duration_seconds(iso_duration):
    """Convertit une durée ISO 8601 (ex: PT8M32S) en secondes."""
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return None


def analyze_duration(videos):
    """Cherche la tranche de durée associée aux meilleures performances."""
    buckets = {
        "0-3 min": [],
        "3-6 min": [],
        "6-10 min": [],
        "10-15 min": [],
        "15+ min": [],
    }
    for v in videos:
        seconds = parse_duration_seconds(v["duration"])
        if seconds is None:
            continue
        minutes = seconds / 60
        if minutes <= 3:
            buckets["0-3 min"].append(v["view_count"])
        elif minutes <= 6:
            buckets["3-6 min"].append(v["view_count"])
        elif minutes <= 10:
            buckets["6-10 min"].append(v["view_count"])
        elif minutes <= 15:
            buckets["10-15 min"].append(v["view_count"])
        else:
            buckets["15+ min"].append(v["view_count"])

    result = {}
    for bucket, views in buckets.items():
        if views:
            result[bucket] = {
                "nb_videos": len(views),
                "avg_views": round(sum(views) / len(views)),
                "max_views": max(views),
            }
    # Trie par vues moyennes décroissantes
    best_bucket = max(result.items(), key=lambda x: x[1]["avg_views"])[0] if result else None
    return {"par_tranche": result, "tranche_la_plus_performante": best_bucket}


def analyze_titles(videos, top_n=20):
    """Extrait les mots et structures les plus fréquents dans les titres performants."""
    # On prend le top N des vidéos les plus vues
    top_videos = sorted(videos, key=lambda v: v["view_count"], reverse=True)[:top_n]

    word_counter = Counter()
    starting_words = Counter()
    has_question_mark = 0
    has_number = 0
    title_lengths = []

    for v in top_videos:
        title = v["title"]
        title_lengths.append(len(title))
        if "?" in title:
            has_question_mark += 1
        if re.search(r"\d", title):
            has_number += 1

        words = re.findall(r"\b[a-zàâäéèêëïîôöùûüç]{3,}\b", title.lower())
        words = [w for w in words if w not in STOPWORDS]
        word_counter.update(words)

        first_words = title.strip().split()[:2]
        if first_words:
            starting_words[" ".join(first_words).lower()] += 1

    return {
        "mots_frequents": word_counter.most_common(15),
        "debuts_de_titre_frequents": starting_words.most_common(10),
        "pct_avec_point_interrogation": round(100 * has_question_mark / len(top_videos)),
        "pct_avec_chiffre": round(100 * has_number / len(top_videos)),
        "longueur_titre_moyenne": round(sum(title_lengths) / len(title_lengths)) if title_lengths else None,
        "exemples_top_titres": [v["title"] for v in top_videos[:10]],
    }


def analyze_narrative_structure(videos, top_n=15):
    """Analyse grossière de la structure narrative des vidéos les plus vues avec transcript."""
    with_transcript = [v for v in videos if v.get("has_transcript") and v.get("transcript")]
    top_with_transcript = sorted(with_transcript, key=lambda v: v["view_count"], reverse=True)[:top_n]

    if not top_with_transcript:
        return {
            "nb_transcripts_analyses": 0,
            "note": "Aucun transcript disponible dans les données collectées.",
        }

    intro_word_counts = []
    twist_keywords = Counter()

    # Mots qui signalent souvent un twist / une révélation
    twist_signals = [
        "mais", "soudain", "puis", "alors", "jusqu'à ce que", "c'est là que",
        "personne ne savait", "la vérité", "en réalité", "finalement",
    ]

    for v in top_with_transcript:
        text = v["transcript"]
        words = text.split()
        total_words = len(words)
        # Longueur de l'intro = les 15% premiers mots
        intro_word_counts.append(round(total_words * 0.15))

        text_lower = text.lower()
        for signal in twist_signals:
            if signal in text_lower:
                twist_keywords[signal] += 1

    avg_total_words = round(
        sum(len(v["transcript"].split()) for v in top_with_transcript) / len(top_with_transcript)
    )
    avg_intro_words = round(sum(intro_word_counts) / len(intro_word_counts))

    return {
        "nb_transcripts_analyses": len(top_with_transcript),
        "longueur_moyenne_script_mots": avg_total_words,
        "longueur_moyenne_intro_mots": avg_intro_words,
        "signaux_de_twist_frequents": twist_keywords.most_common(5),
    }


def build_brief(duration_analysis, title_analysis, narrative_analysis):
    """Condense tout en un brief prêt à injecter dans un prompt de génération IA (Brique 3)."""
    best_duration = duration_analysis.get("tranche_la_plus_performante")
    top_words = [w for w, _ in title_analysis["mots_frequents"][:8]]

    brief = (
        f"Format vidéo optimal : {best_duration or 'non déterminé'}.\n"
        f"Titres performants : longueur moyenne ~{title_analysis['longueur_titre_moyenne']} caractères, "
        f"{title_analysis['pct_avec_chiffre']}% contiennent un chiffre, "
        f"{title_analysis['pct_avec_point_interrogation']}% contiennent un '?'.\n"
        f"Mots-clés/thèmes récurrents dans les titres qui marchent : {', '.join(top_words)}.\n"
    )
    if narrative_analysis.get("nb_transcripts_analyses", 0) > 0:
        brief += (
            f"Structure narrative observée : script d'environ "
            f"{narrative_analysis['longueur_moyenne_script_mots']} mots, "
            f"avec une intro d'environ {narrative_analysis['longueur_moyenne_intro_mots']} mots "
            f"avant que l'histoire ne s'installe.\n"
        )
    return brief


def run():
    print("📂 Chargement des données...")
    videos = load_data()
    print(f"   {len(videos)} vidéos chargées")

    print("\n⏱  Analyse de la durée optimale...")
    duration_analysis = analyze_duration(videos)
    for bucket, stats in duration_analysis["par_tranche"].items():
        print(f"   {bucket}: {stats['nb_videos']} vidéos, {stats['avg_views']:,} vues en moyenne")
    print(f"   → Tranche la plus performante : {duration_analysis['tranche_la_plus_performante']}")

    print("\n📝 Analyse des titres performants...")
    title_analysis = analyze_titles(videos)
    print(f"   Mots les plus fréquents : {title_analysis['mots_frequents'][:8]}")

    print("\n🎬 Analyse de la structure narrative...")
    narrative_analysis = analyze_narrative_structure(videos)
    print(f"   Transcripts analysés : {narrative_analysis['nb_transcripts_analyses']}")

    brief = build_brief(duration_analysis, title_analysis, narrative_analysis)

    output = {
        "duree": duration_analysis,
        "titres": title_analysis,
        "structure_narrative": narrative_analysis,
        "brief_condense": brief,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. Résultat sauvegardé dans '{OUTPUT_FILE}'")
    print("\n--- BRIEF CONDENSÉ (pour la Brique 3) ---")
    print(brief)


if __name__ == "__main__":
    run()

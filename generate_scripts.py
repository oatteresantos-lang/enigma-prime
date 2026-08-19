"""
ENIGMA PRIME - Brique 3 : Génération de scripts pour Shorts
===============================================================

Ce script :
1. Lit le brief de patterns généré par la Brique 2 (patterns_brief.json)
2. Construit un prompt adapté au format Shorts (histoire courte,
   accroche immédiate, twist rapide)
3. Appelle l'API Groq (gratuite) pour générer plusieurs histoires
   horreur/mystère originales
4. Sauvegarde les scripts générés dans un fichier JSON, prêts pour
   la Brique 4 (voix + montage)

Prérequis :
    pip install groq --break-system-packages

Avant de lancer :
    - Crée un compte gratuit sur https://console.groq.com
    - Génère une clé API (section "API Keys")
    - Mets-la dans GROQ_API_KEY (variable d'environnement ou secret GitHub)

Usage :
    python generate_scripts.py
    (patterns_brief.json doit être dans le même dossier, sinon le
    script utilise un brief par défaut)
"""

import json
import os
import re

from groq import Groq

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "COLLE_TA_CLE_API_ICI")

# Modèle Groq utilisé (rapide et gratuit, bon niveau en français)
MODEL = "moonshotai/kimi-k2-instruct-0905"  # non-reasoning, plus fiable que gpt-oss-120b qui vide parfois "content"

# Nombre d'histoires à générer à chaque exécution
NB_HISTOIRES = 5

# Longueur cible pour un Short (en mots) - pour un short de ~45-60 secondes
LONGUEUR_CIBLE_MOTS = "180 à 260"

PATTERNS_FILE = "patterns_brief.json"
OUTPUT_FILE = "scripts_generes.json"

# Brief par défaut si la Brique 2 n'a pas encore tourné ou si le fichier est absent
BRIEF_PAR_DEFAUT = (
    "Format vidéo optimal : moins de 3 minutes (format Short). "
    "Les titres qui marchent sont courts, intrigants, posent une question "
    "ou annoncent un fait choquant. L'histoire doit démarrer immédiatement "
    "dans l'action, sans introduction longue, et se terminer sur un twist "
    "ou une révélation glaçante dans les toutes dernières secondes."
)


def load_brief():
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("brief_condense", BRIEF_PAR_DEFAUT)
    return BRIEF_PAR_DEFAUT


def build_prompt(brief):
    return f"""Tu es un scénariste spécialisé dans les histoires courtes d'horreur et de mystère pour YouTube Shorts, dans le style de la chaîne "ENIGMA PRIME".

Voici ce que l'analyse des vidéos horreur/mystère les plus performantes du moment montre :
{brief}

Écris UNE histoire originale d'horreur ou de mystère, en français, qui respecte ces règles strictes :
- Longueur : {LONGUEUR_CIBLE_MOTS} mots (format Short, pas plus)
- Elle doit démarrer directement dans le vif du sujet, PAS d'introduction lente
- Elle doit contenir un twist, une révélation ou une chute glaçante dans les toutes dernières phrases
- Ton : immersif, à la première personne ou en narration directe, phrases courtes et percutantes
- L'histoire doit être 100% originale (pas une histoire connue ou un plagiat d'une légende urbaine existante)
- N'ajoute AUCUN titre, AUCUNE mise en forme, AUCUN commentaire : uniquement le texte brut de l'histoire

Réponds uniquement avec le texte de l'histoire, rien d'autre."""


def generate_title(client, story_text):
    """Génère un titre accrocheur pour l'histoire, en suivant les patterns de titres performants."""
    prompt = f"""Voici une histoire courte d'horreur/mystère :

{story_text}

Propose UN SEUL titre YouTube Shorts accrocheur pour cette histoire, en français, court (moins de 60 caractères), intrigant, qui donne envie de cliquer. Réponds uniquement avec le titre, sans guillemets, sans rien d'autre."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_completion_tokens=300,
    )
    title = (response.choices[0].message.content or "").strip()
    # Nettoie d'éventuels guillemets ajoutés par le modèle
    title = title.strip('"\'')
    return title


def generate_story(client, brief):
    prompt = build_prompt(brief)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
        max_completion_tokens=1500,
    )
    return (response.choices[0].message.content or "").strip()


def run():
    if GROQ_API_KEY == "COLLE_TA_CLE_API_ICI":
        print("⚠️  Ajoute ta clé API Groq dans GROQ_API_KEY avant de lancer le script.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    brief = load_brief()

    print(f"📋 Brief utilisé :\n{brief}\n")
    print(f"✍️  Génération de {NB_HISTOIRES} histoires...\n")

    scripts = []
    for i in range(NB_HISTOIRES):
        print(f"  [{i + 1}/{NB_HISTOIRES}] Génération de l'histoire...")
        try:
            story = generate_story(client, brief)
            title = generate_title(client, story)
            word_count = len(story.split())

            scripts.append({
                "id": i + 1,
                "title": title,
                "story": story,
                "word_count": word_count,
            })
            print(f"      → \"{title}\" ({word_count} mots)")
        except Exception as e:
            print(f"      ⚠️ Erreur lors de la génération : {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(scripts, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. {len(scripts)} scripts sauvegardés dans '{OUTPUT_FILE}'")


if __name__ == "__main__":
    run()

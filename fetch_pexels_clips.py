"""
ENIGMA PRIME - Brique 4 : Habillage visuel (vidéos de stock Pexels)
====================================================================

Ce script :
1. Lit les histoires générées par la Brique 3 (scripts_generes.json)
2. Extrait des mots-clés visuels pertinents de chaque histoire (via Groq,
   pour rester cohérent avec le reste du pipeline)
3. Interroge l'API Pexels pour chaque histoire et récupère plusieurs
   clips vidéo pertinents (ambiance sombre/horreur/mystère)
4. Télécharge les clips dans un dossier par histoire, prêts pour
   la Brique 5 (voix off) et la Brique 6 (montage)

Prérequis :
    pip install groq requests --break-system-packages

Avant de lancer :
    - Crée un compte gratuit sur https://www.pexels.com/api/
    - Génère une clé API
    - Mets-la dans PEXELS_API_KEY (variable d'environnement ou secret GitHub)

Usage :
    python fetch_pexels_clips.py
    (scripts_generes.json doit être dans le même dossier)
"""

import json
import os
import re
import time

import requests
from groq import Groq

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "COLLE_TA_CLE_API_ICI")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "COLLE_TA_CLE_API_ICI")

MODEL = "moonshotai/kimi-k2-instruct-0905"  # non-reasoning, plus fiable que gpt-oss-120b qui vide parfois "content"

SCRIPTS_FILE = "scripts_generes.json"
OUTPUT_DIR = "clips"
OUTPUT_MANIFEST = "clips_manifest.json"

# Nombre de clips téléchargés par histoire
CLIPS_PAR_HISTOIRE = 3

# Orientation vidéo pour Shorts (portrait)
ORIENTATION = "portrait"

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"


def extract_keywords(client, story_text):
    """Utilise Groq pour extraire des mots-clés visuels (anglais, pour Pexels) depuis l'histoire."""
    prompt = f"""Voici une histoire courte d'horreur/mystère :

{story_text}

Propose 3 mots-clés ou courtes expressions en ANGLAIS décrivant des images ou ambiances visuelles (lieux, objets, atmosphères sombres) qui correspondraient bien à cette histoire pour illustrer une vidéo avec des clips de stock footage. Réponds uniquement avec les 3 mots-clés séparés par des virgules, rien d'autre. Exemple de format : dark forest night, abandoned house, foggy street"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_completion_tokens=200,
    )
    raw = (response.choices[0].message.content or "").strip()
    keywords = [k.strip() for k in raw.split(",") if k.strip()]
    return keywords[:3] if keywords else ["dark atmosphere horror"]


def search_pexels(keyword, per_page=5):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": keyword,
        "orientation": ORIENTATION,
        "per_page": per_page,
    }
    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("videos", [])


def best_video_file(video, max_width=1080):
    """Choisit le fichier vidéo le plus adapté (portrait, qualité raisonnable)."""
    files = video.get("video_files", [])
    portrait_files = [f for f in files if f.get("height", 0) > f.get("width", 0)]
    candidates = portrait_files if portrait_files else files
    candidates = [f for f in candidates if f.get("width", 9999) <= max_width] or candidates
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.get("width", 0))


def download_file(url, dest_path):
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def sanitize_filename(text):
    text = re.sub(r"[^\w\-]", "_", text)
    return text[:50]


def run():
    if PEXELS_API_KEY == "COLLE_TA_CLE_API_ICI":
        print("⚠️  Ajoute ta clé API Pexels dans PEXELS_API_KEY avant de lancer le script.")
        return
    if GROQ_API_KEY == "COLLE_TA_CLE_API_ICI":
        print("⚠️  Ajoute ta clé API Groq dans GROQ_API_KEY avant de lancer le script.")
        return

    if not os.path.exists(SCRIPTS_FILE):
        print(f"⚠️  Fichier '{SCRIPTS_FILE}' introuvable. Lance d'abord la Brique 3.")
        return

    with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
        scripts = json.load(f)

    client = Groq(api_key=GROQ_API_KEY)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    manifest = []

    for script in scripts:
        story_id = script["id"]
        title = script["title"]
        story_text = script["story"]

        print(f"\n🎬 Histoire {story_id} : \"{title}\"")

        try:
            keywords = extract_keywords(client, story_text)
            print(f"   Mots-clés : {keywords}")
        except Exception as e:
            print(f"   ⚠️ Erreur extraction mots-clés : {e}")
            keywords = ["dark atmosphere horror mystery"]

        story_dir = os.path.join(OUTPUT_DIR, f"story_{story_id}_{sanitize_filename(title)}")
        os.makedirs(story_dir, exist_ok=True)

        downloaded = []
        clips_needed = CLIPS_PAR_HISTOIRE

        for keyword in keywords:
            if len(downloaded) >= clips_needed:
                break
            try:
                videos = search_pexels(keyword, per_page=5)
            except Exception as e:
                print(f"   ⚠️ Erreur recherche Pexels pour '{keyword}': {e}")
                continue

            for video in videos:
                if len(downloaded) >= clips_needed:
                    break
                file_info = best_video_file(video)
                if not file_info:
                    continue
                clip_filename = f"clip_{len(downloaded) + 1}.mp4"
                dest_path = os.path.join(story_dir, clip_filename)
                try:
                    download_file(file_info["link"], dest_path)
                    downloaded.append({
                        "file": dest_path,
                        "keyword": keyword,
                        "pexels_video_id": video.get("id"),
                        "duration_seconds": video.get("duration"),
                    })
                    print(f"   ✅ Téléchargé : {clip_filename} (mot-clé: {keyword})")
                except Exception as e:
                    print(f"   ⚠️ Erreur téléchargement : {e}")
                time.sleep(0.5)  # petite pause pour rester sympa avec l'API

        manifest.append({
            "story_id": story_id,
            "title": title,
            "keywords_used": keywords,
            "clips": downloaded,
        })

    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    total_clips = sum(len(m["clips"]) for m in manifest)
    print(f"\n✅ Terminé. {total_clips} clips téléchargés pour {len(manifest)} histoires.")
    print(f"   Manifeste sauvegardé dans '{OUTPUT_MANIFEST}'")


if __name__ == "__main__":
    run()

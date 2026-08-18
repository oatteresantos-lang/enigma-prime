"""
ENIGMA PRIME - Brique 5 : Voix off (Text-to-Speech)
====================================================================

Ce script :
1. Lit les histoires générées par la Brique 3 (scripts_generes.json)
2. Convertit le texte de chaque histoire en voix off (fichier audio .mp3)
   via edge-tts (gratuit, pas de clé API nécessaire)
3. Sauvegarde chaque fichier audio dans le dossier de l'histoire
   correspondante (clips/story_X_titre/voiceover.mp3), prêt pour
   la Brique 6 (montage)
4. Met à jour clips_manifest.json avec le chemin de l'audio et sa durée

Prérequis :
    pip install edge-tts requests --break-system-packages

Usage :
    python generate_voiceover.py
    (scripts_generes.json et clips_manifest.json doivent être présents)
"""

import asyncio
import json
import os
import re
import wave
import contextlib

import edge_tts

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

SCRIPTS_FILE = "scripts_generes.json"
MANIFEST_FILE = "clips_manifest.json"
OUTPUT_DIR = "clips"

# Voix edge-tts. Pour une voix française, dispo : "fr-FR-HenriNeural" (homme)
# ou "fr-FR-DeniseNeural" (femme). Pour l'anglais (souvent préféré pour les
# Shorts horreur/mystère à portée internationale) : "en-US-ChristopherNeural"
# ou "en-US-AriaNeural".
VOICE = "fr-FR-HenriNeural"

# Vitesse et ton (ex: "+10%" plus rapide, "-10%" plus lent, "" par défaut)
RATE = "+0%"
PITCH = "+0Hz"


def sanitize_filename(text):
    text = re.sub(r"[^\w\-]", "_", text)
    return text[:50]


async def generate_audio(text, output_path):
    """Génère un fichier audio à partir d'un texte via edge-tts."""
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)


def get_mp3_duration_seconds(path):
    """Estimation rapide de la durée d'un mp3 via mutagen si dispo, sinon None."""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(path)
        return round(audio.info.length, 1)
    except Exception:
        return None


async def run():
    if not os.path.exists(SCRIPTS_FILE):
        print(f"⚠️  Fichier '{SCRIPTS_FILE}' introuvable. Lance d'abord la Brique 3.")
        return

    with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
        scripts = json.load(f)

    # Charger le manifeste des clips (Brique 4) s'il existe, pour l'enrichir
    manifest = []
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    manifest_by_id = {m["story_id"]: m for m in manifest}

    for script in scripts:
        story_id = script["id"]
        title = script["title"]
        story_text = script["story"]

        story_dir = os.path.join(OUTPUT_DIR, f"story_{story_id}_{sanitize_filename(title)}")
        os.makedirs(story_dir, exist_ok=True)
        audio_path = os.path.join(story_dir, "voiceover.mp3")

        print(f"\n🎙️  Histoire {story_id} : \"{title}\"")
        try:
            await generate_audio(story_text, audio_path)
            duration = get_mp3_duration_seconds(audio_path)
            duration_str = f"{duration}s" if duration else "durée inconnue"
            print(f"   ✅ Voix off générée : {audio_path} ({duration_str})")

            if story_id in manifest_by_id:
                manifest_by_id[story_id]["voiceover"] = {
                    "file": audio_path,
                    "voice": VOICE,
                    "duration_seconds": duration,
                }
            else:
                manifest.append({
                    "story_id": story_id,
                    "title": title,
                    "voiceover": {
                        "file": audio_path,
                        "voice": VOICE,
                        "duration_seconds": duration,
                    },
                })
        except Exception as e:
            print(f"   ⚠️ Erreur génération voix off : {e}")

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. Manifeste mis à jour dans '{MANIFEST_FILE}'")


if __name__ == "__main__":
    asyncio.run(run())

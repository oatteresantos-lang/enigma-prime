"""
ENIGMA PRIME - Brique 6 : Montage automatique (FFmpeg)
====================================================================

Ce script :
1. Lit clips_manifest.json (clips Pexels de la Brique 4 + voix off de la Brique 5)
2. Pour chaque histoire :
   a. Redimensionne/recadre chaque clip en format vertical 1080x1920 (Shorts)
   b. Concatène les clips bout à bout, les boucle/coupe pour couvrir
      exactement la durée de la voix off
   c. Ajoute la piste audio (voix off)
   d. Génère des sous-titres (.srt) en découpant le texte de l'histoire
      en segments répartis uniformément sur la durée de l'audio
   e. Incruste les sous-titres dans la vidéo (burn-in)
3. Sauvegarde la vidéo finale dans clips/story_X_titre/final_video.mp4

Prérequis :
    - ffmpeg installé (préinstallé sur les runners GitHub Actions ubuntu-latest)
    - pip install requests --break-system-packages (déjà présent pour les autres briques)

Usage :
    python generate_video.py
    (scripts_generes.json et clips_manifest.json doivent être présents,
     avec les clips et la voix off déjà générés par les Briques 4 et 5)
"""

import json
import os
import re
import subprocess
import textwrap

SCRIPTS_FILE = "scripts_generes.json"
MANIFEST_FILE = "clips_manifest.json"

# Résolution cible (format Shorts/Reels/TikTok)
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# Nombre de mots par segment de sous-titre (affichage à l'écran)
WORDS_PER_SUBTITLE = 6


def run_ffmpeg(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg a échoué :\n{result.stderr[-2000:]}")
    return result


def get_video_duration(path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(text, total_duration, output_path):
    words = text.split()
    segments = [
        " ".join(words[i:i + WORDS_PER_SUBTITLE])
        for i in range(0, len(words), WORDS_PER_SUBTITLE)
    ]
    if not segments:
        return

    seg_duration = total_duration / len(segments)
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, segment in enumerate(segments):
            start = idx * seg_duration
            end = (idx + 1) * seg_duration
            f.write(f"{idx + 1}\n")
            f.write(f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n")
            f.write(f"{segment}\n\n")


def build_video(clips, voiceover_path, srt_path, output_path, target_duration):
    """
    Redimensionne chaque clip en 1080x1920, les concatène en boucle jusqu'à
    couvrir target_duration, ajoute l'audio et incruste les sous-titres.
    """
    if not clips:
        raise RuntimeError("Aucun clip disponible pour cette histoire.")

    clip_paths = [c["file"] for c in clips if os.path.exists(c["file"])]
    if not clip_paths:
        raise RuntimeError("Aucun fichier clip valide trouvé sur le disque.")

    # Boucler la liste de clips jusqu'à dépasser la durée cible
    looped_clips = []
    total = 0.0
    i = 0
    while total < target_duration:
        clip = clip_paths[i % len(clip_paths)]
        dur = get_video_duration(clip)
        if dur <= 0:
            i += 1
            continue
        looped_clips.append(clip)
        total += dur
        i += 1
        if i > len(clip_paths) * 10:  # garde-fou anti boucle infinie
            break

    # Fichier de concat pour ffmpeg
    concat_list_path = output_path + "_concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for clip in looped_clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    tmp_concat = output_path + "_concat_raw.mp4"
    tmp_scaled = output_path + "_scaled.mp4"

    # 1. Concaténer les clips bruts
    run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c", "copy", tmp_concat,
    ])

    # 2. Redimensionner/recadrer en 1080x1920 et couper à la durée cible
    scale_filter = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
    )
    run_ffmpeg([
        "ffmpeg", "-y", "-i", tmp_concat,
        "-t", str(target_duration),
        "-vf", scale_filter,
        "-an", tmp_scaled,
    ])

    # 3. Ajouter l'audio + incruster les sous-titres
    srt_escaped = srt_path.replace(":", "\\:").replace("'", "\\'")
    subtitles_filter = (
        f"subtitles='{srt_escaped}':force_style="
        "'FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=120'"
    )
    run_ffmpeg([
        "ffmpeg", "-y", "-i", tmp_scaled, "-i", voiceover_path,
        "-vf", subtitles_filter,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest", output_path,
    ])

    # Nettoyage des fichiers temporaires
    for tmp in (concat_list_path, tmp_concat, tmp_scaled):
        if os.path.exists(tmp):
            os.remove(tmp)


def run():
    if not os.path.exists(SCRIPTS_FILE) or not os.path.exists(MANIFEST_FILE):
        print("⚠️  Fichiers requis introuvables. Lance d'abord les Briques 3, 4 et 5.")
        return

    with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
        scripts = {s["id"]: s for s in json.load(f)}

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest:
        story_id = entry["story_id"]
        title = entry.get("title", f"story_{story_id}")
        clips = entry.get("clips", [])
        voiceover = entry.get("voiceover")

        print(f"\n🎞️  Montage histoire {story_id} : \"{title}\"")

        if not voiceover or not os.path.exists(voiceover.get("file", "")):
            print("   ⚠️ Voix off manquante, montage ignoré (lance la Brique 5 d'abord).")
            continue
        if not clips:
            print("   ⚠️ Aucun clip disponible, montage ignoré (lance la Brique 4 d'abord).")
            continue

        story_dir = os.path.dirname(voiceover["file"])
        duration = voiceover.get("duration_seconds") or get_video_duration(voiceover["file"])
        if not duration:
            print("   ⚠️ Impossible de déterminer la durée de la voix off, montage ignoré.")
            continue

        script_text = scripts.get(story_id, {}).get("story", "")
        srt_path = os.path.join(story_dir, "subtitles.srt")
        generate_srt(script_text, duration, srt_path)

        output_path = os.path.join(story_dir, "final_video.mp4")
        try:
            build_video(clips, voiceover["file"], srt_path, output_path, duration)
            print(f"   ✅ Vidéo finale générée : {output_path}")
            entry["final_video"] = output_path
        except Exception as e:
            print(f"   ⚠️ Erreur montage : {e}")

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. Manifeste mis à jour dans '{MANIFEST_FILE}'")


if __name__ == "__main__":
    run()

"""
ENIGMA PRIME - Brique 1 : Détection de patterns viraux (horreur/mystère)
=========================================================================

Ce script :
1. Cherche les vidéos YouTube horreur/mystère les plus vues récemment
   (via YouTube Data API v3 - déjà activée sur ton projet "enigma-prime-505317")
2. Récupère leurs métadonnées (titre, durée, vues, date)
3. Tente de récupérer le transcript (sous-titres) de chaque vidéo pour
   analyser la structure narrative
4. Sauvegarde tout dans un fichier JSON pour analyse (Brique 2)

Prérequis :
    pip install google-api-python-client youtube-transcript-api --break-system-packages

Avant de lancer :
    - Remplace YOUTUBE_API_KEY par ta clé API (celle générée sur le projet Enigma Prime)
    - Ajuste SEARCH_QUERIES selon les thèmes que tu veux surveiller
"""

import json
import os
import time
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

# Mets ta clé API ici, ou en variable d'environnement YOUTUBE_API_KEY
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "COLLE_TA_CLE_API_ICI")

# Requêtes de recherche : à ajuster selon ce que tu veux capter
SEARCH_QUERIES = [
    "histoire horreur vraie",
    "histoire mystère non résolue",
    "creepypasta",
    "légende urbaine effrayante",
    "true horror story",
]

# Ne garder que les vidéos publiées dans les X derniers jours
DAYS_BACK = 90

# Nombre max de résultats par requête (max 50 par appel API)
MAX_RESULTS_PER_QUERY = 25

# Fichier de sortie
OUTPUT_FILE = "viral_horror_data.json"


# ------------------------------------------------------------------
# FONCTIONS
# ------------------------------------------------------------------

def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def search_videos(youtube, query, days_back=DAYS_BACK, max_results=MAX_RESULTS_PER_QUERY):
    """Cherche des vidéos correspondant à la requête, triées par nombre de vues."""
    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat("T") + "Z"

    request = youtube.search().list(
        q=query,
        part="id",
        type="video",
        order="viewCount",
        publishedAfter=published_after,
        maxResults=max_results,
        relevanceLanguage="fr",  # change en "en" si tu veux aussi capter l'anglais
    )
    response = request.execute()
    return [item["id"]["videoId"] for item in response.get("items", [])]


def get_video_details(youtube, video_ids):
    """Récupère les métadonnées détaillées (titre, vues, durée) pour une liste d'IDs."""
    details = []
    # L'API accepte max 50 IDs par appel
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(chunk),
        )
        response = request.execute()
        for item in response.get("items", []):
            details.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", "")[:500],
                "published_at": item["snippet"]["publishedAt"],
                "channel_title": item["snippet"]["channelTitle"],
                "view_count": int(item["statistics"].get("viewCount", 0)),
                "like_count": int(item["statistics"].get("likeCount", 0)),
                "comment_count": int(item["statistics"].get("commentCount", 0)),
                "duration": item["contentDetails"]["duration"],  # format ISO 8601, ex: PT8M32S
            })
    return details


def get_transcript(video_id):
    """Récupère le transcript d'une vidéo si disponible (pour analyser la structure narrative)."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["fr", "en"])
        full_text = " ".join(chunk["text"] for chunk in transcript)
        return full_text
    except (TranscriptsDisabled, NoTranscriptFound, Exception):
        return None


def run():
    if YOUTUBE_API_KEY == "COLLE_TA_CLE_API_ICI":
        print("⚠️  Ajoute ta clé API YouTube dans YOUTUBE_API_KEY avant de lancer le script.")
        return

    youtube = get_youtube_client()
    all_video_ids = set()

    print("🔍 Recherche des vidéos par thème...")
    for query in SEARCH_QUERIES:
        try:
            ids = search_videos(youtube, query)
            print(f"  - '{query}' → {len(ids)} vidéos trouvées")
            all_video_ids.update(ids)
            time.sleep(0.5)  # petite pause pour rester safe côté quota
        except Exception as e:
            print(f"  ⚠️ Erreur sur la requête '{query}': {e}")

    print(f"\n📊 Total vidéos uniques trouvées : {len(all_video_ids)}")
    print("📥 Récupération des métadonnées...")
    videos = get_video_details(youtube, list(all_video_ids))

    # Trie par vues décroissantes
    videos.sort(key=lambda v: v["view_count"], reverse=True)

    print("📝 Récupération des transcripts (peut prendre un moment)...")
    for i, video in enumerate(videos):
        transcript = get_transcript(video["video_id"])
        video["transcript"] = transcript
        video["has_transcript"] = transcript is not None
        if (i + 1) % 10 == 0:
            print(f"  ... {i + 1}/{len(videos)} traitées")
        time.sleep(0.3)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. {len(videos)} vidéos sauvegardées dans '{OUTPUT_FILE}'")
    print(f"   Vidéos avec transcript récupéré : {sum(1 for v in videos if v['has_transcript'])}")
    print("\nTop 5 vidéos les plus vues :")
    for v in videos[:5]:
        print(f"  • {v['view_count']:,} vues — \"{v['title']}\" ({v['channel_title']})")


if __name__ == "__main__":
    run()

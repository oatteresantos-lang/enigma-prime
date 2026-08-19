"""
ENIGMA PRIME - Brique 7 : Upload automatique YouTube
====================================================================

Ce script :
1. Lit clips_manifest.json (vidéos finales montées par la Brique 6)
2. S'authentifie auprès de l'API YouTube via OAuth2 (refresh token stocké
   en secret GitHub, pas d'interaction utilisateur nécessaire)
3. Upload chaque vidéo finale sur la chaîne YouTube, avec un titre et
   une description générés à partir de l'histoire
4. Marque chaque histoire comme "uploadée" dans le manifeste pour éviter
   les doublons lors des runs suivants

Prérequis :
    pip install google-auth google-auth-oauthlib google-api-python-client

Variables d'environnement requises :
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Usage :
    python upload_youtube.py
"""

import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCRIPTS_FILE = "scripts_generes.json"
MANIFEST_FILE = "clips_manifest.json"

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Visibilité par défaut des vidéos uploadées.
# "private" pour tester sans publier publiquement, "public" une fois validé.
PRIVACY_STATUS = "public"

# Catégorie YouTube "Entertainment" (voir la liste des IDs via l'API si besoin)
CATEGORY_ID = "24"


def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def build_description(story_text):
    # Description courte + hashtags, tronquée pour rester lisible
    snippet = story_text[:300].rsplit(" ", 1)[0] + "..."
    return f"{snippet}\n\n#horreur #mystere #shorts"


def upload_video(youtube, video_path, title, description):
    body = {
        "snippet": {
            "title": title[:100],  # limite YouTube
            "description": description,
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Upload en cours : {int(status.progress() * 100)}%")

    return response.get("id")


def run():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("⚠️  Variables YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN manquantes.")
        return

    if not os.path.exists(MANIFEST_FILE):
        print(f"⚠️  Fichier '{MANIFEST_FILE}' introuvable. Lance d'abord les Briques précédentes.")
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scripts = {}
    if os.path.exists(SCRIPTS_FILE):
        with open(SCRIPTS_FILE, "r", encoding="utf-8") as f:
            scripts = {s["id"]: s for s in json.load(f)}

    youtube = get_youtube_client()

    for entry in manifest:
        story_id = entry["story_id"]
        title = entry.get("title", f"Histoire {story_id}")
        final_video = entry.get("final_video")

        print(f"\n📤 Histoire {story_id} : \"{title}\"")

        if entry.get("youtube_video_id"):
            print(f"   ⏭️ Déjà uploadée (ID: {entry['youtube_video_id']}), ignorée.")
            continue

        if not final_video or not os.path.exists(final_video):
            print("   ⚠️ Vidéo finale introuvable, upload ignoré (lance la Brique 6 d'abord).")
            continue

        story_text = scripts.get(story_id, {}).get("story", "")
        description = build_description(story_text) if story_text else ""

        try:
            video_id = upload_video(youtube, final_video, title, description)
            entry["youtube_video_id"] = video_id
            entry["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
            print(f"   ✅ Uploadée : {entry['youtube_url']} (visibilité: {PRIVACY_STATUS})")
        except Exception as e:
            print(f"   ⚠️ Erreur upload : {e}")

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé. Manifeste mis à jour dans '{MANIFEST_FILE}'")


if __name__ == "__main__":
    run()

import argparse
import os
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from requests import RequestException

SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
PLAYLIST_ITEMS = "https://www.googleapis.com/youtube/v3/playlistItems"
CREDENTIALS = Path.home() / ".config" / "ytptube-playlist-cleanup" / "credentials.json"
VIDEO_ARCHIVE_ID = re.compile(r"youtube ([A-Za-z0-9_-]{11})")
TIMEOUT = 15
MAX_PAGES = 100
MAX_REMOVALS = 50


def completed_videos(database: Path, download_root: Path) -> dict[str, datetime]:
	root = download_root.resolve(strict=True)
	with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as connection:
		rows = connection.execute("""
			SELECT created_at, json_extract(data, '$.archive_id'), json_extract(data, '$.download_dir'),
				json_extract(data, '$.filename'), json_extract(data, '$.file_size')
			FROM history
			WHERE type = 'done' AND json_extract(data, '$.status') = 'finished'
				AND coalesce(json_extract(data, '$.download_skipped'), 0) = 0
			ORDER BY created_at
		""").fetchall()

	completed = {}
	for finished, archive_id, directory, filename, expected_size in rows:
		match = VIDEO_ARCHIVE_ID.fullmatch(archive_id or "")
		if not match or not directory or not filename:
			continue
		path = (Path(directory) / filename).resolve()
		if not path.is_relative_to(root) or not path.is_file():
			continue
		size = path.stat().st_size
		if size > 0 and (not expected_size or size == expected_size):
			completed[match[1]] = datetime.fromisoformat(finished).replace(tzinfo=UTC)
	return completed


def playlist_entries(session: AuthorizedSession, playlist_id: str) -> list[dict]:
	params = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
	entries = []
	for _ in range(MAX_PAGES):
		response = session.get(PLAYLIST_ITEMS, params=params, timeout=TIMEOUT)
		response.raise_for_status()
		page = response.json()
		entries.extend(page["items"])
		if not (token := page.get("nextPageToken")):
			return entries
		params["pageToken"] = token
	raise ValueError("Playlist exceeded the page limit")


def matching_entries(entries: list[dict], completed: dict[str, datetime], playlist_id: str) -> list[dict]:
	matches = []
	for entry in entries:
		snippet = entry["snippet"]
		if snippet["playlistId"] != playlist_id:
			raise ValueError("YouTube returned an entry from a different playlist")
		finished = completed.get(snippet["resourceId"].get("videoId", ""))
		if finished and datetime.fromisoformat(snippet["publishedAt"]) < finished:
			matches.append(entry)
	return matches


def authorize(client: Path, credentials: Path) -> None:
	credentials.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
	if credentials.exists():
		raise FileExistsError(credentials)
	flow = InstalledAppFlow.from_client_secrets_file(str(client), [SCOPE], autogenerate_code_verifier=True)
	token = flow.run_local_server(host="127.0.0.1", port=49317, timeout_seconds=180, prompt="consent")
	if not token.refresh_token:
		raise ValueError("Google did not return a refresh token")
	fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
	with os.fdopen(fd, "w") as output:
		output.write(token.to_json())


def main() -> int:
	parser = argparse.ArgumentParser(description="Remove downloaded entries from one YouTube playlist.")
	parser.add_argument("--credentials", type=Path, default=CREDENTIALS)
	modes = parser.add_subparsers(dest="mode", required=True)
	auth = modes.add_parser("authorize")
	auth.add_argument("desktop_client", type=Path)
	clean = modes.add_parser("clean")
	clean.add_argument("playlist_id")
	clean.add_argument("database", type=Path)
	clean.add_argument("download_root", type=Path)
	clean.add_argument("--apply", action="store_true")
	args = parser.parse_args()

	try:
		if args.mode == "authorize":
			authorize(args.desktop_client, args.credentials)
			return 0

		completed = completed_videos(args.database, args.download_root)
		with AuthorizedSession(
			Credentials.from_authorized_user_file(str(args.credentials), [SCOPE])
		) as session:
			matches = matching_entries(
				playlist_entries(session, args.playlist_id), completed, args.playlist_id
			)
			if not args.apply:
				print(f"{len(matches)} matching playlist entries")
				for entry in matches:
					print(entry["snippet"]["title"])
				return 0

			for entry in matches[:MAX_REMOVALS]:
				response = session.delete(PLAYLIST_ITEMS, params={"id": entry["id"]}, timeout=TIMEOUT)
				if response.status_code != 404:
					response.raise_for_status()
				print(f"Cleared playlist entry {entry['id']}")
	except (GoogleAuthError, RequestException, OSError, ValueError, sqlite3.Error) as error:
		print(f"Playlist cleanup failed: {error}", file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

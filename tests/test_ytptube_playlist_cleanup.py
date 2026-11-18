import runpy
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

script = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ytptube-playlist-cleanup.py"))
completed_videos = script["completed_videos"]
matching_entries = script["matching_entries"]


def entry(video_id, added, playlist="lata"):
	return {
		"snippet": {
			"playlistId": playlist,
			"publishedAt": added,
			"resourceId": {"videoId": video_id},
		},
	}


class CleanupTest(unittest.TestCase):
	def test_older_failed_and_later_readded_entries_stay(self):
		finished = datetime(2026, 11, 18, 12, tzinfo=UTC)
		entries = [
			entry("failed", "2026-11-17T11:00:00Z"),
			entry("downloaded", "2026-11-18T11:00:00Z"),
			entry("downloaded", "2026-11-18T13:00:00Z"),
		]
		self.assertEqual(matching_entries(entries, {"downloaded": finished}, "lata"), [entries[1]])

	def test_unexpected_playlist_fails_before_removal(self):
		with self.assertRaises(ValueError):
			matching_entries([entry("video", "2026-11-18T11:00:00Z", "other")], {}, "lata")

	def test_requires_a_finished_video_with_the_recorded_file(self):
		with TemporaryDirectory() as temporary:
			directory = Path(temporary)
			root = directory / "downloads"
			root.mkdir()
			(root / "complete.mp4").write_bytes(b"12345")
			(root / "partial.mp4").write_bytes(b"123")
			database = directory / "ytptube.db"
			with sqlite3.connect(database) as connection:
				connection.execute("CREATE TABLE history (type, data, created_at)")
				connection.executemany(
					"""
					INSERT INTO history VALUES ('done',
						json_object('status', ?, 'archive_id', ?, 'download_dir', ?,
							'filename', ?, 'file_size', 5, 'download_skipped', ?),
						'2026-11-18 12:00:00')
					""",
					[
						("finished", "youtube complete-ID", str(root), "complete.mp4", 0),
						("finished", "youtube partial--ID", str(root), "partial.mp4", 0),
						("finished", "youtube missing--ID", str(root), "missing.mp4", 0),
						("error", "youtube failed---ID", str(root), "complete.mp4", 0),
						("finished", "youtube skipped--ID", str(root), "complete.mp4", 1),
					],
				)
			self.assertEqual(
				completed_videos(database, root), {"complete-ID": datetime(2026, 11, 18, 12, tzinfo=UTC)}
			)


if __name__ == "__main__":
	unittest.main()

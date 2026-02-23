#!/usr/bin/env python3
"""
Generate detailed Apple Notes attachment report with actionable recommendations.

This script creates:
1. HTML report with interactive filtering
2. CSV export for spreadsheet analysis
3. Deletion recommendations based on size and type
"""

import csv
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def get_human_readable_size(bytes_val):
	"""Convert bytes to human readable format."""
	for unit in ["B", "KB", "MB", "GB", "TB"]:
		if bytes_val < 1024:
			return f"{bytes_val:.2f} {unit}"
		bytes_val /= 1024
	return f"{bytes_val:.2f} PB"


def analyze_database():
	"""Extract attachment data from NoteStore.sqlite."""
	db_path = Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"

	if not db_path.exists():
		print(f"❌ Database not found at {db_path}")
		return None

	try:
		conn = sqlite3.connect(str(db_path))
		conn.row_factory = sqlite3.Row
		cursor = conn.cursor()

		query = """
		SELECT
			obj.Z_PK AS object_id,
			obj.ZFILENAME AS filename,
			obj.ZTITLE AS title,
			obj.ZTYPEUTI AS mime_type,
			obj.ZFILESIZE AS file_size,
			obj.ZMODIFICATIONDATE AS modification_date,
			obj.ZNOTE AS note_fk,
			COALESCE(note.ZTITLE1, '(Untitled)') AS note_title,
			note.Z_PK AS note_id,
			note.ZIDENTIFIER AS note_uuid
		FROM ZICCLOUDSYNCINGOBJECT obj
		LEFT JOIN ZICCLOUDSYNCINGOBJECT note ON obj.ZNOTE = note.Z_PK
		WHERE obj.ZFILESIZE > 0
		ORDER BY obj.ZFILESIZE DESC
		"""

		cursor.execute(query)
		results = [dict(row) for row in cursor.fetchall()]

		# Also fetch note identifiers for deep linking
		note_ids_query = """
		SELECT Z_PK, ZIDENTIFIER, ZTITLE1
		FROM ZICCLOUDSYNCINGOBJECT
		WHERE ZTYPE IS NULL AND ZTITLE1 IS NOT NULL
		"""
		cursor.execute(note_ids_query)
		note_identifiers = {row[0]: {"id": row[1], "title": row[2]} for row in cursor.fetchall()}

		conn.close()

		return results, note_identifiers
	except sqlite3.OperationalError as e:
		print(f"❌ Cannot access database: {e}")
		print("\nYou need to grant Full Disk Access to Terminal:")
		print("  1. System Settings > Security & Privacy > Privacy")
		print("  2. Full Disk Access > + button > Terminal.app")
		return None


def get_file_extension(mime_type):
	"""Get common file extension from MIME type."""
	mime_to_ext = {
		"public.jpeg": "jpg",
		"public.png": "png",
		"public.heic": "heic",
		"public.tiff": "tiff",
		"com.adobe.pdf": "pdf",
		"public.mpeg-4": "mp4",
		"com.apple.quicktime-movie": "mov",
		"com.apple.m4a-audio": "m4a",
		"public.data": "data",
	}
	return mime_to_ext.get(mime_type, mime_type.split(".")[-1] if mime_type else "unknown")


def get_notes_app_deep_link(note_uuid):
	"""Generate a deep link to open a note in the Notes app."""
	if not note_uuid:
		return None
	return f"notes://showNote?identifier={note_uuid}"


def categorize_by_type_size(attachments):
	"""Identify large attachments by type for recommendations."""
	by_type = defaultdict(lambda: {"count": 0, "total_size": 0, "files": []})

	for att in attachments:
		mime_type = att.get("mime_type") or "unknown"
		size = att.get("file_size", 0)

		by_type[mime_type]["count"] += 1
		by_type[mime_type]["total_size"] += size
		by_type[mime_type]["files"].append(
			{
				"filename": att.get("filename") or att.get("title") or f"Object_{att.get('object_id')}",
				"size": size,
				"note": att.get("note_title", "Untitled"),
				"object_id": att.get("object_id"),
				"note_uuid": att.get("note_uuid"),
			}
		)

	return by_type


def generate_csv_report(attachments, output_path):
	"""Generate detailed CSV report."""
	sorted_files = sorted(attachments, key=lambda x: x.get("file_size", 0), reverse=True)

	with open(output_path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerow(
			["note_title", "attachment_name", "size_bytes", "size_human", "mime_type", "object_id"]
		)

		for att in sorted_files:
			writer.writerow(
				[
					att.get("note_title") or "(Untitled)",
					att.get("filename") or att.get("title") or f"Object_{att.get('object_id')}",
					att.get("file_size", 0),
					get_human_readable_size(att.get("file_size", 0)),
					att.get("mime_type", "unknown"),
					att.get("object_id"),
				]
			)

	print(f"✅ CSV report: {output_path}")


def generate_html_report(attachments, output_path):
	"""Generate interactive HTML report grouped by note."""
	total_size = sum(att.get("file_size", 0) for att in attachments)
	total_count = len(attachments)

	# Count unique file types
	file_types = set(att.get("mime_type", "unknown") for att in attachments)
	num_file_types = len(file_types)

	# Group attachments by note
	notes_dict = {}
	for att in attachments:
		note_title = att.get("note_title") or "(Untitled)"
		note_uuid = att.get("note_uuid")

		if note_title not in notes_dict:
			notes_dict[note_title] = {"uuid": note_uuid, "size": 0, "files": []}

		notes_dict[note_title]["size"] += att.get("file_size", 0)
		notes_dict[note_title]["files"].append(
			{
				"filename": att.get("filename") or att.get("title") or f"Object_{att.get('object_id')}",
				"size": att.get("file_size", 0),
			}
		)

	# Sort notes by total size (largest first)
	sorted_notes = sorted(notes_dict.items(), key=lambda x: x[1]["size"], reverse=True)

	html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Apple Notes Attachment Report</title>
	<style>
		* {{
			margin: 0;
			padding: 0;
			box-sizing: border-box;
		}}

		body {{
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
			background: #f5f5f5;
			color: #333;
			line-height: 1.6;
		}}

		header {{
			background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			color: white;
			padding: 20px;
			text-align: center;
		}}

		header h1 {{
			font-size: 1.8em;
			margin: 0;
		}}

		header p {{
			font-size: 0.9em;
			margin: 5px 0 0 0;
			opacity: 0.9;
		}}

		.container {{
			max-width: 100%;
			margin: 0;
			padding: 0;
		}}

		.summary {{
			display: flex;
			background: white;
			border-bottom: 1px solid #ddd;
			padding: 0;
		}}

		.card {{
			flex: 1;
			padding: 15px 20px;
			border-right: 1px solid #ddd;
			text-align: center;
		}}

		.card:last-child {{
			border-right: none;
		}}

		.card h3 {{
			color: #667eea;
			margin: 0 0 5px 0;
			font-size: 0.75em;
			text-transform: uppercase;
			letter-spacing: 0.5px;
		}}

		.card .value {{
			font-size: 1.5em;
			font-weight: bold;
			color: #333;
			margin: 0;
		}}

		.types-section {{
			margin: 30px 0;
		}}

		.types-section h2 {{
			margin: 0;
			padding: 20px;
			font-size: 1.1em;
			background: #f9f9f9;
			border-bottom: 1px solid #ddd;
		}}

		.file-list {{
			background: white;
			overflow-y: auto;
			max-height: 80vh;
		}}

		.note-group {{
			border-bottom: 1px solid #ddd;
			padding: 16px 20px;
			background: white;
		}}

		.note-group:hover {{
			background: #fafafa;
		}}

		.note-header {{
			display: grid;
			grid-template-columns: 2fr 1fr;
			gap: 40px;
			align-items: center;
			margin-bottom: 12px;
		}}

		.note-title {{
			font-weight: 600;
			font-size: 1em;
			color: #333;
		}}

		.note-title a {{
			color: #667eea;
			text-decoration: none;
			cursor: pointer;
			font-weight: 600;
		}}

		.note-title a:hover {{
			color: #764ba2;
			text-decoration: underline;
		}}

		.note-size {{
			font-weight: bold;
			color: #667eea;
			text-align: right;
			font-size: 0.95em;
		}}

		.note-files {{
			font-family: 'Monaco', 'Courier New', monospace;
			font-size: 0.85em;
			color: #666;
			white-space: pre-wrap;
			word-break: break-word;
			line-height: 1.4;
			margin-left: 0;
			padding: 0;
		}}

		.note-link-icon {{
			margin-left: 4px;
			font-size: 0.8em;
		}}



		footer {{
			text-align: center;
			padding: 20px;
			color: #999;
			font-size: 0.85em;
			background: #f9f9f9;
			border-top: 1px solid #ddd;
		}}

		@media (max-width: 768px) {{
			header h1 {{
				font-size: 1.8em;
			}}

			.type-header {{
				flex-direction: column;
				align-items: flex-start;
			}}

			.type-stats {{
				width: 100%;
				margin-top: 10px;
			}}
		}}
	</style>
</head>
<body>
	<header>
		<h1>📱 Apple Notes Attachment Analysis</h1>
		<p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
	</header>

	<div class="container">
		<div class="summary">
			<div class="card">
				<h3>Files</h3>
				<div class="value">{total_count:,}</div>
			</div>
			<div class="card">
				<h3>Total Size</h3>
				<div class="value">{get_human_readable_size(total_size)}</div>
			</div>
			<div class="card">
				<h3>Types</h3>
				<div class="value">{num_file_types}</div>
			</div>
			<div class="card">
				<h3>Avg</h3>
				<div class="value">{get_human_readable_size(total_size // max(total_count, 1))}</div>
			</div>
		</div>



		<div class="types-section">
			<h2>Notes by Storage</h2>
			<div class="file-list">
"""

	# Add notes grouped by size with their files
	for note_title, note_data in sorted_notes:
		note_uuid = note_data["uuid"]
		total_note_size = note_data["size"]
		files = sorted(note_data["files"], key=lambda x: x["size"], reverse=True)

		if note_uuid:
			note_link = get_notes_app_deep_link(note_uuid)
			note_display = f'<a href="{note_link}" title="Click to open this note in Notes.app">{note_title}<span class="note-link-icon">↗</span></a>'
		else:
			note_display = note_title

		# Build file list (newline separated)
		files_text = "\n".join([f["filename"] for f in files])

		html += f"""
			<div class="note-group">
				<div class="note-header">
					<div class="note-title">{note_display}</div>
					<div class="note-size">{get_human_readable_size(total_note_size)}</div>
				</div>
				<div class="note-files">{files_text}</div>
			</div>
"""

	html += """
		</div>
	</div>

	<footer>
		<p>Click any note name to open in Notes.app</p>
	</footer>
</body>
</html>
"""

	with open(output_path, "w", encoding="utf-8") as f:
		f.write(html)

	print(f"✅ HTML report: {output_path}")


def main():
	print("🔍 Generating Apple Notes attachment report...\n")

	# Analyze database
	print("📚 Analyzing database...")
	result = analyze_database()

	if result is None:
		return

	db_attachments, note_identifiers = result

	print(f"   Found {len(db_attachments)} attachments\n")

	# Generate reports
	output_dir = Path.cwd()

	# CSV Report
	csv_path = output_dir / "notes_attachment_detailed.csv"
	generate_csv_report(db_attachments, csv_path)

	# HTML Report
	html_path = output_dir / "notes_attachment_report.html"
	generate_html_report(db_attachments, html_path)

	print("\n" + "=" * 80)
	print("✅ Reports generated successfully!")
	print("=" * 80)
	print(f"\n📄 Files created:")
	print(f"   1. {html_path.name} - Open in your browser for interactive view")
	print(f"   2. {csv_path.name} - Import into spreadsheet for detailed analysis")
	print(f"\n💡 Next steps:")
	print(f"   1. Review the HTML report to identify large attachments")
	print(f"   2. Use the CSV for sorting and filtering in Excel/Sheets")
	print(f"   3. Delete large attachments from Notes app")
	print(f"   4. Re-run analyze-notes-space.py to verify cleanup\n")


if __name__ == "__main__":
	main()

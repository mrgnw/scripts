#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#   "ffmpeg-python",
#   "rich",
#   "tqdm",
# ]
# ///

import ffmpeg
import sys
from pathlib import Path
import time
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from tqdm import tqdm
import re


def get_video_duration(input_file):
	probe = ffmpeg.probe(input_file)
	duration = float(probe["format"]["duration"])
	return duration


def main():
	if len(sys.argv) != 2:
		print("Usage: vrscene.py <video_file>")
		sys.exit(1)

	input_file = sys.argv[1]
	duration = get_video_duration(input_file)

	with Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn()) as progress:
		task = progress.add_task("Detecting scenes...", total=duration)

		stream = (
			ffmpeg.input(input_file)
			.filter("crop", w="iw/2", h="ih", x=0, y=0)
			.filter("select", expr="gt(scene,0.4)")
			.filter("showinfo")
		)

		process = ffmpeg.output(stream, "null", f="null").overwrite_output().run_async(pipe_stderr=True)

		timestamps = []

		while True:
			line = process.stderr.readline().decode()
			if not line:
				break

			if "pts_time" in line:
				timestamp = float(line.split("pts_time:")[1].split()[0])
				timestamps.append(timestamp)
				progress.update(task, completed=timestamp)

		process.wait()
		progress.update(task, completed=duration)

		if not timestamps:
			print("No scenes detected")
			sys.exit(1)

		# Create chapters file
		task = progress.add_task("Creating chapters...", total=len(timestamps))
		chapters_file = Path(input_file).parent / "chapters.txt"
		print(f"Creating chapters file: {chapters_file}")

		with open(chapters_file, "w") as f:
			for i, timestamp in enumerate(timestamps, 1):
				f.write(f"CHAPTER{i:02d}=00:{int(timestamp//60):02d}:{timestamp%60:06.3f}\n")
				f.write(f"CHAPTER{i:02d}NAME=Scene {i}\n")
				progress.update(task, advance=1)

		# Apply chapters
		output_file = Path(input_file).parent / f"chaptered_{Path(input_file).name}"
		print(f"Creating output file: {output_file}")
		task = progress.add_task("Applying chapters...", total=duration)

		stream = ffmpeg.input(input_file)
		process = (
			ffmpeg.output(stream, str(output_file), i=str(chapters_file), map_chapters=0, codec="copy")
			.overwrite_output()
			.run_async(pipe_stderr=True)
		)

		while True:
			line = process.stderr.readline().decode()
			if not line:
				break

			time_match = re.search(r"time=(\d+:\d+:\d+.\d+)", line)
			progress_match = re.search(r"progress=(\w+)", line)

			if time_match:
				time_str = time_match.group(1)
				h, m, s = map(float, time_str.split(":"))
				current_time = h * 3600 + m * 60 + s
				progress.update(task, completed=current_time)
			elif progress_match and progress_match.group(1) == "end":
				progress.update(task, completed=duration)
				break

		process.wait()
		progress.update(task, completed=duration)
		print(f"\nDone! Output saved as {output_file}")


if __name__ == "__main__":
	main()

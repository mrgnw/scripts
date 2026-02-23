use anyhow::{Context, Result};
use clap::Parser;
use image::{DynamicImage, GenericImageView, ImageBuffer, ImageFormat, Rgb, RgbImage};
use rayon::prelude::*;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Parser)]
#[command(name = "stitch-rs")]
#[command(about = "Stitch image frames into HD 1080p video")]
struct Args {
	/// Directory containing image frames
	directory: PathBuf,

	/// Output video path (default: output.mp4)
	#[arg(short, long)]
	output: Option<PathBuf>,

	/// Frames per second (default: 30)
	#[arg(short, long, default_value_t = 30)]
	fps: u32,

	/// Output width (default: 1920)
	#[arg(long, default_value_t = 1920)]
	width: u32,

	/// Output height (default: 1080)
	#[arg(long, default_value_t = 1080)]
	height: u32,
}

#[derive(Debug)]
struct Orientations {
	portrait: usize,
	landscape: usize,
	square: usize,
}

fn is_supported_image(path: &Path) -> bool {
	if let Some(ext) = path.extension() {
		let ext = ext.to_string_lossy().to_lowercase();
		matches!(
			ext.as_str(),
			"jpg" | "jpeg" | "png" | "bmp" | "tiff" | "tif" | "webp" | "jxl" | "avif"
		)
	} else {
		false
	}
}

fn load_jxl(path: &Path) -> Result<DynamicImage> {
	let mut file = File::open(path)?;
	let mut data = Vec::new();
	file.read_to_end(&mut data)?;
	
	let decoder = jxl_oxide::JxlImage::builder()
		.read(data.as_slice())
		.map_err(|e| anyhow::anyhow!("Failed to decode JXL: {}", e))?;
	
	let render = decoder.render_frame(0)
		.map_err(|e| anyhow::anyhow!("Failed to render JXL frame: {}", e))?;
	
	let rgb = render.image_all_channels();
	
	let width = rgb.width() as u32;
	let height = rgb.height() as u32;
	let buf = rgb.buf();
	
	let mut rgb_data = Vec::with_capacity((width * height * 3) as usize);
	for &pixel in buf.iter() {
		let val: f32 = pixel;
		rgb_data.push((val.clamp(0.0, 1.0) * 255.0) as u8);
	}
	
	let img = RgbImage::from_raw(width, height, rgb_data)
		.context("Failed to create image from JXL data")?;
	
	Ok(DynamicImage::ImageRgb8(img))
}



fn analyze_images(dir: &Path) -> Result<(Vec<PathBuf>, Orientations)> {
	let mut image_files: Vec<PathBuf> = std::fs::read_dir(dir)
		.context("Failed to read directory")?
		.filter_map(|entry| entry.ok())
		.map(|entry| entry.path())
		.filter(|path| path.is_file() && is_supported_image(path))
		.collect();

	if image_files.is_empty() {
		anyhow::bail!("No image files found in {:?}", dir);
	}

	image_files.sort();

	let mut orientations = Orientations {
		portrait: 0,
		landscape: 0,
		square: 0,
	};

	for path in &image_files {
		if let Ok(img) = image::open(path) {
			let (width, height) = img.dimensions();
			if width > height {
				orientations.landscape += 1;
			} else if height > width {
				orientations.portrait += 1;
			} else {
				orientations.square += 1;
			}
		}
	}

	Ok((image_files, orientations))
}

fn process_image(
	img_path: &Path,
	idx: usize,
	output_dir: &Path,
	target_width: u32,
	target_height: u32,
) -> Result<()> {
	let img = if let Some(ext) = img_path.extension() {
		let ext = ext.to_string_lossy().to_lowercase();
		if ext == "jxl" {
			load_jxl(img_path)?
		} else {
			image::open(img_path)
				.with_context(|| format!("Failed to open image: {:?}", img_path))?
		}
	} else {
		image::open(img_path)
			.with_context(|| format!("Failed to open image: {:?}", img_path))?
	};

	let (img_width, img_height) = img.dimensions();

	// Calculate scaling to fit within target dimensions
	let scale = (target_width as f32 / img_width as f32)
		.min(target_height as f32 / img_height as f32);

	let new_width = (img_width as f32 * scale) as u32;
	let new_height = (img_height as f32 * scale) as u32;

	// Resize image
	let img_resized = img.resize(new_width, new_height, image::imageops::FilterType::Lanczos3);

	// Create black background at target resolution
	let mut background: ImageBuffer<Rgb<u8>, Vec<u8>> =
		ImageBuffer::from_pixel(target_width, target_height, Rgb([0, 0, 0]));

	// Calculate position to center the image
	let x_offset = (target_width - new_width) / 2;
	let y_offset = (target_height - new_height) / 2;

	// Convert resized image to RGB8
	let img_rgb = img_resized.to_rgb8();

	// Paste resized image onto background
	image::imageops::overlay(&mut background, &img_rgb, x_offset as i64, y_offset as i64);

	// Save with sequential numbering for ffmpeg
	let output_path = output_dir.join(format!("frame_{:06}.jpg", idx));
	background.save_with_format(&output_path, ImageFormat::Jpeg)
		.context("Failed to save processed frame")?;

	Ok(())
}

fn process_images(
	image_files: &[PathBuf],
	output_dir: &Path,
	target_width: u32,
	target_height: u32,
) -> Result<()> {
	std::fs::create_dir_all(output_dir).context("Failed to create output directory")?;

	image_files
		.par_iter()
		.enumerate()
		.try_for_each(|(idx, img_path)| {
			process_image(img_path, idx, output_dir, target_width, target_height)
		})?;

	Ok(())
}

fn create_video(frames_dir: &Path, output_path: &Path, fps: u32) -> Result<()> {
	let frame_pattern = frames_dir.join("frame_%06d.jpg");

	let status = Command::new("ffmpeg")
		.args([
			"-framerate",
			&fps.to_string(),
			"-i",
			&frame_pattern.to_string_lossy(),
			"-c:v",
			"libx264",
			"-pix_fmt",
			"yuv420p",
			"-crf",
			"18",
			"-y",
			&output_path.to_string_lossy(),
		])
		.status()
		.context("Failed to run ffmpeg. Make sure ffmpeg is installed.")?;

	if !status.success() {
		anyhow::bail!("ffmpeg failed with status: {}", status);
	}

	println!("\nVideo created: {}", output_path.display());

	Ok(())
}

fn main() -> Result<()> {
	let args = Args::parse();

	if !args.directory.is_dir() {
		anyhow::bail!("{:?} is not a directory", args.directory);
	}

	let output_path = args.output.unwrap_or_else(|| PathBuf::from("output.mp4"));

	println!("Analyzing images in {:?}...", args.directory);
	let (image_files, orientations) = analyze_images(&args.directory)?;

	println!("\nFound {} images:", image_files.len());
	println!("  Landscape: {}", orientations.landscape);
	println!("  Portrait: {}", orientations.portrait);
	println!("  Square: {}", orientations.square);
	println!("\nTarget resolution: {}x{}", args.width, args.height);
	println!("Frame rate: {} fps\n", args.fps);

	let temp_dir = tempfile::tempdir().context("Failed to create temporary directory")?;
	let temp_path = temp_dir.path();

	println!("Processing images in parallel...");
	process_images(&image_files, temp_path, args.width, args.height)?;
	println!("Processed {} frames", image_files.len());

	println!("\nCreating video with ffmpeg...");
	create_video(temp_path, &output_path, args.fps)?;

	Ok(())
}

import os
import sys
import re
import json
import argparse
from dotenv import load_dotenv

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# Add scripts directory to path
scripts_dir = os.path.join(BASE_DIR, 'scripts')
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.gemini_helper import generate_script
from scripts.tts_helper import generate_voiceovers
from scripts.video_helper import assemble_video

# Load environment variables from .env if present
load_dotenv()

def extract_pdf_pages(pdf_path, output_dir):
    """
    Extracts all pages of a PDF file as images into the output_dir.
    """
    import fitz  # PyMuPDF
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[INFO] Opening PDF file: {pdf_path}")
    doc = fitz.open(pdf_path)
    print(f"[INFO] Extracting {len(doc)} pages from PDF (dpi=150)...")
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img_path = os.path.join(output_dir, f"{page_num+1:03d}.png")
        pix.save(img_path)
        
    print(f"[INFO] Successfully extracted all PDF pages to: {output_dir}")

def natural_sort_key(s):
    """
    Sorts strings with numbers in a natural way (e.g., '2.jpg' before '10.jpg').
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_config():
    """
    Loads configuration settings from config.json.
    """
    config_path = os.path.join(BASE_DIR, 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}. Using defaults.")
    return {}

def main():
    # Fix Windows console encoding for Devnagari text
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        
    parser = argparse.ArgumentParser(description="Hindi Manhwa Shorts & Videos Automation Pipeline")
    parser.add_argument("--chapter-dir", type=str, required=True, 
                        help="Path to folder containing chapter images")
    parser.add_argument("--output", type=str, default=None,
                        help="Path to save the output video MP4 file (or directory if splitting)")
    parser.add_argument("--voice", type=str, default=None,
                        help="Edge TTS voice model override")
    parser.add_argument("--format", type=str, choices=["vertical", "horizontal"], default="vertical",
                        help="Layout format: vertical (9:16) or horizontal (16:9)")
    parser.add_argument("--duration", type=str, choices=["30s", "60s", "90s", "full"], default="60s",
                        help="Target duration limit per video")
    parser.add_argument("--split-parts", action="store_true",
                        help="Split the chapter into two distinct parts (Option B)")
    parser.add_argument("--mock-gemini", action="store_true",
                        help="Skip Gemini API and use a mock Hinglish manhwa script for testing")
    parser.add_argument("--music-path", type=str, default=None,
                        help="Path to background music file to mix")
    parser.add_argument("--music-volume", type=float, default=None,
                        help="Volume factor for background music (defaults to config value or 0.10)")
    args = parser.parse_args()
    
    # Verify input directory
    chapter_dir = os.path.abspath(args.chapter_dir)
    
    # Check if the path is a PDF file
    if chapter_dir.lower().endswith('.pdf'):
        if not os.path.isfile(chapter_dir):
            print(f"Error: PDF file '{chapter_dir}' does not exist.")
            sys.exit(1)
        temp_pdf_dir = os.path.abspath(os.path.join(BASE_DIR, 'generated', 'temp', 'pdf_pages'))
        try:
            extract_pdf_pages(chapter_dir, temp_pdf_dir)
            chapter_dir = temp_pdf_dir
        except Exception as e:
            print(f"Error: Failed to process PDF: {e}")
            sys.exit(1)
    elif not os.path.isdir(chapter_dir):
        print(f"Error: Chapter directory '{chapter_dir}' does not exist.")
        sys.exit(1)
        
    # Gather and sort images
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    image_filenames = [f for f in os.listdir(chapter_dir) if f.lower().endswith(valid_exts)]
    if not image_filenames:
        print(f"Error: No valid images (.jpg, .jpeg, .png, .webp) found in '{chapter_dir}'.")
        sys.exit(1)
        
    image_filenames = sorted(image_filenames, key=natural_sort_key)
    image_paths = [os.path.join(chapter_dir, f) for f in image_filenames]
    print(f"Found {len(image_paths)} chapter images in '{os.path.basename(chapter_dir)}'.")
    
    # Load settings
    config = load_config()
    music_volume = args.music_volume if args.music_volume is not None else config.get("video", {}).get("bg_music_volume", 0.10)
    
    # Find Gemini API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = config.get("gemini", {}).get("api_key")
        
    if not api_key and not args.mock_gemini:
        print("\n[ERROR] Gemini API Key not found!")
        print("Please do one of the following:")
        print("  1. Set the environment variable: 'setx GEMINI_API_KEY your_key'")
        print("  2. Place it in config.json under 'gemini.api_key'")
        print("  3. Create a '.env' file in this folder and add: GEMINI_API_KEY=your_key\n")
        sys.exit(1)
        
    model_name = config.get("gemini", {}).get("model", "gemini-2.5-flash")
    tts_voice = args.voice or config.get("tts", {}).get("voice", "hi-IN-MadhurNeural")
    
    print("\n--- STEP 1: Story Understanding & Script Generation via Gemini ---")
    if args.mock_gemini:
        print("[INFO] Using Mock Gemini script...")
        # Create mock script response
        if args.split_parts:
            print("[INFO] Generating mock script for 2 parts...")
            mock_parts = [
                {
                    "part_number": 1,
                    "part_title": "Part 1: Secret Power",
                    "segments": [
                        {"voice_text": "सब लोग इस शिकारी को कमजोर समझते थे...", "subtitle_text": "sab log is hunter ko sabse kamzor samajhte the...", "image_file": "001.jpg"},
                        {"voice_text": "लेकिन डंगऑन के अंदर उसे एक सीक्रेट पॉवर मिली।", "subtitle_text": "lekin dungeon ke andar use ek secret power mili.", "image_file": "002.jpg"},
                        {"voice_text": "तभी उसके सामने एक भयानक मॉन्स्टर आ गया! क्या वह बचेगा?", "subtitle_text": "tabhi uske saamne ek bhayanak monster aa gaya! kya woh bachega?", "image_file": "003.jpg"}
                    ]
                },
                {
                    "part_number": 2,
                    "part_title": "Part 2: The Battle",
                    "segments": [
                        {"voice_text": "पिछले पार्ट में हमने देखा, शिकारी मुसीबत में था।", "subtitle_text": "pichle part mein humne dekha, hunter museebat mein tha.", "image_file": "003.jpg"},
                        {"voice_text": "लेकिन उसने अपनी नई गॉड-लेवल एबिलिटी को एक्टिवेट कर दिया!", "subtitle_text": "lekin usne apni nayi god-level ability ko activate kar diya!", "image_file": "004.jpg"},
                        {"voice_text": "एक ही वार में मॉन्स्टर खत्म! पर आगे क्या होगा? सब्सक्राइब करें!", "subtitle_text": "ek hi waar mein monster khatam! par aage kya hoga? subscribe karein!", "image_file": "005.jpg"}
                    ]
                }
            ]
        else:
            print("[INFO] Generating mock script for 1 part...")
            mock_parts = [
                {
                    "part_number": 1,
                    "part_title": "Full Chapter",
                    "segments": [
                        {"voice_text": "सब लोग इस शिकारी को कमजोर समझते थे...", "subtitle_text": "sab log is hunter ko sabse kamzor samajhte the...", "image_file": "001.jpg"},
                        {"voice_text": "लेकिन डंगऑन के अंदर उसे एक सीक्रेट पॉवर मिली।", "subtitle_text": "lekin dungeon ke andar use ek secret power mili.", "image_file": "002.jpg"},
                        {"voice_text": "उसने अकेले ही सारे मॉन्सटर्स का खात्मा कर दिया!", "subtitle_text": "usne akele hi saare monsters ka khatma kar diya!", "image_file": "003.jpg"},
                        {"voice_text": "अब कोई भी उसके सामने टिक नहीं सकता था।", "subtitle_text": "ab koi bhi uske saamne tik nahi sakta tha.", "image_file": "004.jpg"},
                        {"voice_text": "लेकिन असली ट्विस्ट तो अभी बाकी है... क्या वह जिंदा बच पाएगा?", "subtitle_text": "lekin asli twist toh abhi baaki hai... kya woh zinda bach payega?", "image_file": "005.jpg"}
                    ]
                }
            ]
        script_data = {"parts": mock_parts}
    else:
        try:
            script_data = generate_script(
                image_paths, 
                api_key, 
                model_name=model_name,
                video_format=args.format,
                target_duration=args.duration,
                split_parts=args.split_parts
            )
        except Exception as e:
            print(f"Failed to generate script from Gemini: {e}")
            sys.exit(1)
            
    parts = script_data.get("parts", [])
    if not parts:
        print("Error: Gemini returned an empty response (no parts found).")
        sys.exit(1)
        
    print(f"\nSuccessfully generated {len(parts)} parts.")
    
    # Process each part
    for part in parts:
        part_num = part.get("part_number", 1)
        part_title = part.get("part_title", f"Part {part_num}")
        segments = part.get("segments", [])
        
        print(f"\n================ PROCESSING: {part_title} ================")
        if not segments:
            print(f"Warning: No segments found in {part_title}. Skipping.")
            continue
            
        print("\nGenerated Script Beats:")
        for idx, seg in enumerate(segments):
            # Resolve image filename to full path
            img_fn = seg["image_file"]
            full_img_path = os.path.join(chapter_dir, img_fn)
            if not os.path.exists(full_img_path):
                print(f"Warning: Gemini mapped to non-existent image '{img_fn}'. Auto-mapping sequentially.")
                full_img_path = image_paths[min(idx, len(image_paths) - 1)]
                
            seg["image_file"] = full_img_path
            print(f"[{idx+1}/{len(segments)}] Image: {os.path.basename(full_img_path)}")
            print(f"   Voice (Devnagari): {seg['voice_text']}")
            print(f"   Subtitle (Hinglish): {seg['subtitle_text']}")
            print("-" * 50)
            
        # Determine output file path for this part
        folder_name = os.path.basename(chapter_dir)
        format_suffix = "horizontal" if args.format == "horizontal" else "shorts"
        
        if args.output:
            if args.split_parts:
                # If split parts is enabled, output should be a folder or format names based on part_num
                base, ext = os.path.splitext(args.output)
                if ext: # It's a file path
                    output_path = f"{base}_part{part_num}{ext}"
                else: # It's a directory
                    output_path = os.path.join(args.output, f"{folder_name}_part{part_num}_{format_suffix}.mp4")
            else:
                output_path = os.path.abspath(args.output)
        else:
            suffix = f"_part{part_num}" if args.split_parts else ""
            output_path = os.path.abspath(os.path.join(
                BASE_DIR, 'generated', 'videos', 
                f"{folder_name}{suffix}_{format_suffix}.mp4"
            ))
            
        temp_audio_dir = os.path.join(BASE_DIR, 'generated', 'temp', f'audio_part{part_num}')
        
        print(f"\n--- STEP 2: Voice Narration & Word-Level Timing (Part {part_num}) ---")
        try:
            segments_with_audio = generate_voiceovers(segments, temp_audio_dir, voice=tts_voice)
        except Exception as e:
            print(f"Failed to generate voiceovers: {e}")
            continue
            
        print(f"\n--- STEP 3: Video Rendering (Part {part_num}) ---")
        try:
            assemble_video(
                segments_with_audio, output_path, config, 
                video_format=args.format, 
                bg_music_path=args.music_path, 
                bg_music_volume=music_volume
            )
            print(f"\n[SUCCESS] Part {part_num} successfully created!")
            print(f"Saved to: {output_path}")
        except Exception as e:
            print(f"Failed during video assembly for Part {part_num}: {e}")
            continue
            
    print("\nAll parts processed!")

if __name__ == "__main__":
    main()

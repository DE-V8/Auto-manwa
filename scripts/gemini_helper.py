import os
import json
from PIL import Image
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional


class ScriptSegment(BaseModel):
    voice_text: str = Field(
        description="The Hindi narration text to be spoken, written in Devnagari script "
                    "(e.g., 'सब लोग इसे कमजोर समझते थे...'). Keep sentences short, dramatic, and punchy."
    )
    subtitle_text: str = Field(
        description="The Hinglish subtitle text to display on screen, written in Latin script "
                    "(e.g., 'Sab log ise kamzor samajhte the...'). This must match the voice_text exactly in meaning."
    )
    image_file: str = Field(
        description="The exact filename of the image from the provided chapter images that represents this scene."
    )


class VideoPart(BaseModel):
    part_number: int = Field(description="The number of this video part (e.g., 1 or 2).")
    part_title: str = Field(
        description="A short, catchy Hinglish/English title for this part "
                    "(e.g., 'Part 1: Secret Power' or 'Part 2: The Battle')."
    )
    segments: List[ScriptSegment] = Field(
        description="The sequence of narrative scenes for this video part."
    )


class ManhwaScriptResponse(BaseModel):
    parts: List[VideoPart] = Field(description="The list of video parts generated from the chapter(s).")


def generate_script(
    image_paths: List[str],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    video_format: str = "vertical",
    target_duration: str = "60s",
    split_parts: bool = False,
    chapter_boundaries: Optional[List[int]] = None,
) -> dict:
    """
    Sends chapter images to Gemini and requests a structured Hinglish/Devnagari script.

    Args:
        image_paths:         Flat list of ALL image paths across all chapters (in order).
        api_key:             Gemini API key.
        model_name:          Gemini model to use.
        video_format:        'vertical' or 'horizontal'.
        target_duration:     '30s', '60s', '90s', or 'full'.
        split_parts:         If True, split output into 2 video parts.
        chapter_boundaries:  List of start-indices for each chapter in image_paths.
                             e.g. [0, 45, 90] means ch1 starts at 0, ch2 at 45, ch3 at 90.
                             If None / single chapter, no boundary markers are inserted.
    """
    if not api_key:
        raise ValueError("Gemini API key is required. Set it in config.json or environment variables.")

    client = genai.Client(api_key=api_key)

    # Build chapter boundary set for marker insertion
    boundary_set = set(chapter_boundaries[1:]) if chapter_boundaries and len(chapter_boundaries) > 1 else set()
    num_chapters = len(chapter_boundaries) if chapter_boundaries else 1

    contents = []
    print(f"Loading {len(image_paths)} images across {num_chapters} chapter(s) for Gemini...")

    for i, path in enumerate(image_paths):
        # Insert chapter boundary marker before first image of each new chapter
        if i in boundary_set:
            ch_num = chapter_boundaries.index(i)  # 0-indexed chapter number
            marker = f"\n--- CHAPTER {ch_num + 1} STARTS HERE ---\n"
            contents.append(marker)
            print(f"[INFO] Chapter boundary inserted before image index {i} (Chapter {ch_num + 1})")

        try:
            img = Image.open(path)
            max_size = 1600
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size))

            filename = os.path.basename(path)
            contents.append(f"Image Filename: {filename}")
            contents.append(img)
        except Exception as e:
            print(f"Warning: Failed to load image {path}: {e}")

    # Duration guidance
    duration_prompt = ""
    if target_duration == "30s":
        duration_prompt = "Keep the script to ~60-70 words per part (3-4 punchy sentences), for a fast-paced 30-second video."
    elif target_duration == "60s":
        duration_prompt = "Keep the script to ~120-130 words per part (5-7 sentences), for a 60-second video."
    elif target_duration == "90s":
        duration_prompt = "Keep the script to ~180-200 words per part (7-9 sentences), for a 90-second video."
    else:
        duration_prompt = "Write a comprehensive recap of all events, sequential and detailed, without strict word limits."

    # Parts guidance
    parts_prompt = ""
    if split_parts:
        parts_prompt = """
        You MUST split the story into exactly 2 video parts:
        - Part 1: Cover the first half of the events. Set up characters, conflict, and suspense. End on a high-tension cliffhanger.
        - Part 2: Resolve the cliffhanger, show the climax / major fight or power reveal, end on a final hook that makes viewers want more.
        """
    else:
        parts_prompt = "Generate exactly 1 video part containing a cohesive recap of all chapter events."

    # Multi-chapter extra instruction
    multi_chapter_instruction = ""
    if num_chapters > 1:
        multi_chapter_instruction = f"""
        You are analyzing {num_chapters} chapters together. The images are divided into chapters with 
        '--- CHAPTER N STARTS HERE ---' markers. Your goal is to create ONE cohesive, dramatic narrative 
        arc spanning all chapters — not separate summaries for each chapter. Connect events naturally, 
        build momentum across chapter boundaries, and treat the whole thing as a single epic recap.
        """

    prompt = f"""
    You are an expert viral YouTube Shorts and anime recap scriptwriter for a Hindi Manhwa Channel.
    Analyze the sequential manhwa chapter images provided. Select the most exciting and dramatic path through the story.

    Format: {video_format.upper()} format.
    {multi_chapter_instruction}
    {parts_prompt}
    {duration_prompt}

    Rules:
    - Keep sentences short, fast-paced, and highly dramatic.
    - Write voice_text in pure Hindi Devnagari script (e.g., "सब लोग इसे कमजोर समझते थे..."). This is for TTS to speak.
    - Write subtitle_text in Hinglish (Latin characters, e.g., "Sab log ise kamzor samajhte the..."). This is for on-screen subtitles.
    - IMPORTANT: Keep each subtitle_text segment SHORT — maximum 8-10 words. Long subtitles cause display problems.
    - Map each script segment to the exact filename of the image that best represents it.
    """
    contents.append(prompt)

    print("Calling Gemini API...")
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ManhwaScriptResponse,
            temperature=0.2
        ),
    )

    return json.loads(response.text)

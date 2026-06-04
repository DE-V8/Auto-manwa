import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from moviepy import VideoClip, AudioFileClip, concatenate_videoclips


# ---------------------------------------------------------------------------
# Text / subtitle utilities
# ---------------------------------------------------------------------------

def draw_text_with_outline(draw, xy, text, font, fill_color, stroke_color, stroke_width):
    x, y = xy
    try:
        draw.text((x, y), text, font=font, fill=fill_color,
                  stroke_width=stroke_width, stroke_fill=stroke_color)
    except TypeError:
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
        draw.text((x, y), text, font=font, fill=fill_color)


def _measure_text(draw, text, font):
    """Safe text width measurement across Pillow versions."""
    try:
        return draw.textlength(text, font=font)
    except AttributeError:
        return font.getsize(text)[0]


def _font_height(font):
    """Return the pixel height of one line for the given font."""
    try:
        # Pillow >= 10
        ascent, descent = font.getmetrics()
        return ascent + descent
    except AttributeError:
        return font.getsize("Ag")[1]


def wrap_words_to_lines(words, draw, font, max_width):
    """
    Split `words` into lines so that each rendered line fits inside max_width.
    Returns list-of-lists: [[word, word, ...], [word, ...], ...]
    """
    lines = []
    current_line = []
    current_w = 0

    for word in words:
        test_str = (" ".join(current_line + [word])) if current_line else word
        test_w = _measure_text(draw, test_str, font)
        if test_w <= max_width or not current_line:
            current_line.append(word)
            current_w = test_w
        else:
            lines.append(current_line)
            current_line = [word]
            current_w = _measure_text(draw, word, font)

    if current_line:
        lines.append(current_line)

    return lines


def draw_pill_background(frame_img, x, y, w, h, radius=14, alpha=160):
    """
    Draw a semi-transparent rounded rectangle (pill) onto frame_img in-place.
    Uses RGBA compositing so it works on top of any background.
    """
    padding_x = 18
    padding_y = 8
    rect_x0 = int(x - padding_x)
    rect_y0 = int(y - padding_y)
    rect_x1 = int(x + w + padding_x)
    rect_y1 = int(y + h + padding_y)

    # Clamp to image bounds
    img_w, img_h = frame_img.size
    rect_x0 = max(0, rect_x0)
    rect_y0 = max(0, rect_y0)
    rect_x1 = min(img_w, rect_x1)
    rect_y1 = min(img_h, rect_y1)

    overlay = Image.new("RGBA", frame_img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle(
        [rect_x0, rect_y0, rect_x1, rect_y1],
        radius=radius,
        fill=(0, 0, 0, alpha)
    )
    # Composite onto frame (must be RGBA temporarily)
    if frame_img.mode != "RGBA":
        frame_img = frame_img.convert("RGBA")
    frame_img = Image.alpha_composite(frame_img, overlay)
    return frame_img.convert("RGB")


# ---------------------------------------------------------------------------
# Core subtitle drawing — 2-line karaoke with pill backgrounds
# ---------------------------------------------------------------------------

def draw_karaoke_subtitles(frame_img, words, word_timestamps, t,
                            font, highlight_color, canvas_w, canvas_h,
                            stroke_color=(0, 0, 0), stroke_width=3,
                            sub_y_bottom_margin=60):
    """
    Draws karaoke-style subtitles with:
    - Auto-wrapped lines (max ~40% of canvas width per line)
    - Semi-transparent pill behind each line for contrast
    - Highlighted (accent color) word for the currently spoken word
    - White for other words
    - Up to 2 lines visible at a time
    """
    if not words:
        return frame_img

    # Determine which word is active right now
    active_word_idx = -1
    for idx, wt in enumerate(word_timestamps):
        if wt["start"] <= t <= wt["end"]:
            active_word_idx = idx
            break

    if active_word_idx == -1 and word_timestamps:
        if t < word_timestamps[0]["start"]:
            active_word_idx = 0
        else:
            active_word_idx = len(word_timestamps) - 1

    if active_word_idx == -1:
        return frame_img

    # Use a temporary draw for measurement only
    tmp_draw = ImageDraw.Draw(frame_img)
    max_line_width = int(canvas_w * 0.88)
    line_h = _font_height(font)
    line_gap = int(line_h * 0.25)

    # Wrap all words into lines
    all_lines = wrap_words_to_lines(words, tmp_draw, font, max_line_width)

    # Find which line the active word lives in, and flatten word→line mapping
    word_global_idx = 0
    line_of_active = 0
    word_offset_in_line = 0
    for li, line_words in enumerate(all_lines):
        for wi, w in enumerate(line_words):
            if word_global_idx == active_word_idx:
                line_of_active = li
                word_offset_in_line = wi
            word_global_idx += 1

    # Show a window of 2 lines centred on the active line
    start_line = max(0, line_of_active - 1)
    end_line = min(len(all_lines), start_line + 2)
    if end_line - start_line < 2 and end_line < len(all_lines):
        end_line = start_line + 2
    visible_lines = all_lines[start_line:end_line]

    # Flatten visible lines back to global word indices for highlight check
    # Build a map: visible_line_word → global_word_index
    flat_global = []
    gi = sum(len(all_lines[i]) for i in range(start_line))
    for vl in visible_lines:
        line_indices = list(range(gi, gi + len(vl)))
        flat_global.append(line_indices)
        gi += len(vl)

    # Total block height
    n_lines = len(visible_lines)
    total_block_h = n_lines * line_h + (n_lines - 1) * line_gap

    # Position: anchor from bottom
    block_y_start = canvas_h - sub_y_bottom_margin - total_block_h

    color_white = (255, 255, 255)

    for li, (line_words, global_indices) in enumerate(zip(visible_lines, flat_global)):
        line_y = block_y_start + li * (line_h + line_gap)

        # Measure full line width for centering
        line_str = " ".join(line_words)
        line_w = _measure_text(tmp_draw, line_str, font)
        line_x_start = (canvas_w - line_w) / 2

        # Draw pill background behind this line
        frame_img = draw_pill_background(
            frame_img,
            x=line_x_start, y=line_y,
            w=line_w, h=line_h
        )

        # Redraw on updated frame
        draw = ImageDraw.Draw(frame_img)
        tmp_draw = draw  # keep reference updated

        # Draw word-by-word with highlight
        cursor_x = line_x_start
        for wi, (word, gidx) in enumerate(zip(line_words, global_indices)):
            word_str = word + (" " if wi < len(line_words) - 1 else "")
            word_w = _measure_text(draw, word_str, font)

            if gidx == active_word_idx:
                fill = highlight_color
                sw = stroke_width + 1   # slightly thicker stroke on highlight
            else:
                fill = color_white
                sw = stroke_width

            draw_text_with_outline(draw, (cursor_x, line_y), word_str, font, fill, stroke_color, sw)
            cursor_x += word_w

    return frame_img


# ---------------------------------------------------------------------------
# Segment clip builder
# ---------------------------------------------------------------------------

def make_segment_clip(segment: dict, config: dict, video_format: str = "vertical") -> VideoClip:
    """
    Creates a VideoClip for a single segment, applying panning/zooming to the image,
    binding the Edge TTS audio, and drawing karaoke-style subtitles.
    Supports both horizontal (16:9) and vertical (9:16) formats.
    """
    img_path = segment["image_file"]
    audio_path = segment["audio_file"]
    subtitle_text = segment["subtitle_text"]
    word_timestamps = segment["word_timestamps"]

    # Load audio to get exact duration
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    # Pre-process image
    base_img = Image.open(img_path).convert("RGB")

    # Video target resolution based on format
    if video_format == "horizontal":
        target_w = 1920
        target_h = 1080
        default_font_size = 45
        sub_bottom_margin = 55
    else:
        target_w = 1080
        target_h = 1920
        default_font_size = 55
        sub_bottom_margin = 80

    zoom_intensity = config.get("video", {}).get("zoom_intensity", 0.08)

    # Font path setup
    font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arialbd.ttf')
    if not os.path.exists(font_path):
        font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')

    font_size = config.get("video", {}).get("subtitle_fontsize", default_font_size)
    if video_format == "horizontal" and font_size > 50:
        font_size = 45  # Cap for horizontal

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    words = subtitle_text.split()

    # Parse highlight (accent) color
    color_hex = config.get("video", {}).get("subtitle_color", "#FFFF00").lstrip('#')
    try:
        highlight_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        highlight_color = (255, 255, 0)

    stroke_width = config.get("video", {}).get("subtitle_stroke_width", 3)

    # Scale image to match target width/height keeping aspect ratio
    aspect = base_img.width / base_img.height

    if video_format == "horizontal":
        new_h = target_h
        new_w = int(new_h * aspect)
    else:
        new_w = target_w
        new_h = int(new_w / aspect)

    # Pre-resize the image using LANCZOS once
    resized_img = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Background logic: blur background if there are padding bars
    needs_bg = False
    if video_format == "horizontal" and new_w < target_w:
        needs_bg = True
    elif video_format == "vertical" and new_h < target_h:
        needs_bg = True

    if needs_bg:
        bg_w = target_w
        bg_h = int(bg_w / aspect) if video_format == "vertical" else int(bg_w / aspect)
        if bg_h < target_h:
            bg_h = target_h
            bg_w = int(bg_h * aspect)

        bg_img = base_img.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
        left = (bg_w - target_w) // 2
        top = (bg_h - target_h) // 2
        bg_img = bg_img.crop((left, top, left + target_w, top + target_h))
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(30))
    else:
        bg_img = None

    def make_frame(t):
        if bg_img is not None:
            frame = bg_img.copy()
            scale = 1.0 + zoom_intensity * (t / duration)
            zoom_w = int(resized_img.width * scale)
            zoom_h = int(resized_img.height * scale)
            zoomed_img = resized_img.resize((zoom_w, zoom_h), Image.Resampling.BILINEAR)

            paste_x = (target_w - zoom_w) // 2
            paste_y = (target_h - zoom_h) // 2
            frame.paste(zoomed_img, (paste_x, paste_y))
        else:
            # Long webtoon strip: scroll vertically from top to bottom
            progress = t / duration
            max_scroll = max(0, new_h - target_h)
            y1 = int(progress * max_scroll)
            frame = resized_img.crop((0, y1, target_w, y1 + target_h))

        # ---- Karaoke subtitle rendering ----
        frame = draw_karaoke_subtitles(
            frame_img=frame,
            words=words,
            word_timestamps=word_timestamps,
            t=t,
            font=font,
            highlight_color=highlight_color,
            canvas_w=target_w,
            canvas_h=target_h,
            stroke_color=(0, 0, 0),
            stroke_width=stroke_width,
            sub_y_bottom_margin=sub_bottom_margin
        )

        return np.array(frame)

    segment_clip = VideoClip(make_frame, duration=duration)
    segment_clip = segment_clip.with_audio(audio_clip)
    return segment_clip


# ---------------------------------------------------------------------------
# Video assembly
# ---------------------------------------------------------------------------

def assemble_video(segments: list, output_path: str, config: dict,
                   video_format: str = "vertical",
                   bg_music_path: str = None,
                   bg_music_volume: float = 0.10):
    """
    Concatenates clips generated from each segment and writes out the final MP4 video.
    Supports mixing background music and attempts GPU-accelerated rendering.
    """
    clips = []
    print(f"Creating video clips for {len(segments)} segments in {video_format} format...")

    for segment in segments:
        clip = make_segment_clip(segment, config, video_format)
        clips.append(clip)

    print("Concatenating clips...")
    final_clip = concatenate_videoclips(clips, method="compose")

    # Mix background music if provided
    if bg_music_path and os.path.exists(bg_music_path):
        try:
            from moviepy.audio.fx import AudioLoop, MultiplyVolume
            from moviepy import CompositeAudioClip

            print(f"Mixing background music: {os.path.basename(bg_music_path)} at volume {bg_music_volume}...")
            voice_audio = final_clip.audio
            music_clip = AudioFileClip(bg_music_path)
            music_clip = music_clip.with_effects([
                AudioLoop(duration=voice_audio.duration),
                MultiplyVolume(bg_music_volume)
            ])
            combined_audio = CompositeAudioClip([voice_audio, music_clip])
            final_clip = final_clip.with_audio(combined_audio)
        except Exception as e:
            print(f"[WARNING] Failed to mix background music: {e}")

    # Save the output file
    fps = config.get("video", {}).get("fps", 24)
    preset = config.get("video", {}).get("ffmpeg_preset", "ultrafast")
    use_gpu = config.get("video", {}).get("use_gpu", True)
    cpu_threads = max(2, (os.cpu_count() or 4) - 1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    gpu_success = False
    if use_gpu:
        try:
            print(f"[GPU] Attempting NVENC GPU-accelerated rendering (h264_nvenc, preset=p1)...")
            final_clip.write_videofile(
                output_path,
                fps=fps,
                codec="h264_nvenc",
                audio_codec="aac",
                ffmpeg_params=["-preset", "p1", "-tune", "ll", "-b:v", "5M"]
            )
            gpu_success = True
            print(f"[GPU] ✅ GPU rendering complete!")
        except Exception as e:
            print(f"[WARNING] GPU NVENC rendering failed: {e}")
            print(f"[INFO] Falling back to CPU rendering...")

    if not gpu_success:
        print(f"[CPU] Rendering with libx264 (preset={preset}, threads={cpu_threads})...")
        final_clip.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset=preset,
            threads=cpu_threads
        )
        print(f"[CPU] ✅ CPU rendering complete!")

    # Clean up resources
    for clip in clips:
        clip.close()
    final_clip.close()
    if 'music_clip' in locals():
        music_clip.close()
    print("Video rendering complete!")

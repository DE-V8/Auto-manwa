import asyncio
import os
import edge_tts

async def generate_speech_for_segment(text: str, voice: str, audio_path: str) -> list:
    """
    Generates speech for a single segment of text and extracts word-level timestamps.
    Returns a list of dictionaries with word, start, and end times in seconds.
    """
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    
    words_data = []
    
    with open(audio_path, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Offset and duration are in 100-nanosecond units (1 tick = 10^-7 sec)
                start_sec = chunk["offset"] / 10000000.0
                duration_sec = chunk["duration"] / 10000000.0
                end_sec = start_sec + duration_sec
                words_data.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": end_sec
                })
                
    return words_data

def generate_voiceovers(segments: list, output_dir: str, voice: str = "hi-IN-MadhurNeural") -> list:
    """
    Synchronous wrapper to generate audio files and word timestamps for all segments.
    Adds audio_file and word_timestamps to each segment dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    updated_segments = []
    for i, segment in enumerate(segments):
        audio_filename = f"segment_{i:03d}.mp3"
        audio_path = os.path.join(output_dir, audio_filename)
        
        print(f"Generating voiceover for segment {i+1}/{len(segments)}...")
        
        # We run the async TTS generator
        words_data = loop.run_until_complete(
            generate_speech_for_segment(segment["voice_text"], voice, audio_path)
        )
        
        # Clone segment data and append results
        new_segment = dict(segment)
        new_segment["audio_file"] = audio_path
        new_segment["word_timestamps"] = words_data
        updated_segments.append(new_segment)
        
    loop.close()
    return updated_segments

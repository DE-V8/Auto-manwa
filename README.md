# AtoManwa — Hindi Manga Video Generator

**Version**: 1.0 | **Platform**: Windows 10/11 (64-bit)

---

## 📦 Installation (No Python needed!)

1. Download `AtoManwa.zip`
2. Extract anywhere (e.g. `C:\AtoManwa\`)
3. Double-click **`AtoManwa.exe`**

That's it — no installation, no Python, no pip.

---

## ⚙️ First-Time Setup

When the app opens:

1. **Get a Gemini API Key** (free):
   - Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
   - Click **"Create API Key"** → copy it

2. Paste your key into the **"Gemini API Key"** field in the app

3. Click **"Save Settings"**

4. **Disable Mock Mode** (the toggle switch) to use real AI generation

---

## 🎬 How to Generate a Video

### Single Chapter
1. Click **"Browse Folder / PDF"** and select your chapter images folder
2. Choose Layout (Shorts or Horizontal), Duration, Music
3. Click **"▶ START GENERATION"**

### Multi-Chapter (2-3 chapters → 1 combined video)
1. Click **"➕ Add to Queue"** and select Chapter 1's folder
2. Click **"➕ Add to Queue"** again for Chapter 2 (and optionally Chapter 3)
3. Click **"▶ START GENERATION"**

Output videos are saved inside the `generated/videos/` folder next to `AtoManwa.exe`.

---

## 🔧 Requirements

| Requirement | Details |
|---|---|
| **FFmpeg** | Required for video rendering. [Download here](https://ffmpeg.org/download.html) and add to PATH |
| **Internet** | Required for Gemini AI (script) and Edge TTS (voice) |
| **Windows** | 10 or 11, 64-bit |
| **RAM** | 4 GB minimum, 8 GB recommended |

### Installing FFmpeg
1. Download `ffmpeg-release-essentials.zip` from [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
2. Extract to `C:\ffmpeg\`
3. Add `C:\ffmpeg\bin` to your System PATH

---

## 📁 Folder Structure (after extract)

```
AtoManwa/
├── AtoManwa.exe          ← Run this
├── config.json           ← Your settings (auto-saved)
├── data/
│   ├── music/            ← Drop .mp3 files here for background music
│   └── sample_chapter/   ← Test images
├── generated/
│   ├── videos/           ← Output videos saved here
│   └── temp/             ← Temporary audio files (auto-cleaned)
└── tools/
    └── comics-downloader.exe  ← Optional: auto-download chapters from URL
```

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| App won't open | Run as Administrator, or allow in Windows Defender |
| "ffmpeg not found" | Install FFmpeg and add to PATH (see above) |
| "API Key invalid" | Check your key at aistudio.google.com |
| Black screen / no video | Check the log panel for errors |
| TTS fails | Requires internet. Check your connection |

---

## 📞 Support

Created for YouTube content creators. For issues, check the Pipeline Logs inside the app.

# Hindi Manhwa Shorts Automation Project

## Project Overview

### Objective

Build a Hindi Manhwa Shorts channel capable of publishing 2–3 YouTube Shorts daily with minimal manual work.

The initial focus is:

* Rapid audience growth
* Content validation
* Low operating cost
* Process automation

The goal is NOT to build a perfect automated system immediately.

The goal is to identify which content performs well before investing heavily in infrastructure.

---

# Phase 1: Validation Stage

Duration: 30 Days

### Primary Goal

Determine whether there is audience demand.

### Success Metrics

* 60–90 Shorts published
* At least one Short reaches 10,000+ views
* First 100 subscribers
* Identify highest-performing niche

### Daily Upload Target

* 2–3 Shorts/day
* 30–60 seconds each

---

# Content Strategy

## Recommended Niches

### Tier 1

* Dungeon/System
* Overpowered Main Character
* Regression

### Tier 2

* Murim
* Revenge Stories

### Avoid Initially

* Romance
* Slice of Life
* Complex Political Stories

---

# Shorts Format

## Structure

### Hook (0–3 sec)

Example:

"सब लोग इसे कमजोर समझते थे..."

### Conflict (3–20 sec)

Explain the problem.

### Power Reveal (20–45 sec)

Most exciting moment.

### Cliffhanger (45–60 sec)

Example:

"लेकिन असली ट्विस्ट अभी बाकी था..."

---

# Automation Architecture

## Pipeline

Manhwa Source

↓

Chapter Images

↓

Story Extraction

↓

Summary Generation

↓

Hindi Script Generation

↓

Voice Generation

↓

Subtitle Generation

↓

Short Video Creation

↓

Upload Queue

↓

YouTube

---

# System Components

## Module 1: Chapter Collection

### Input

* Chapter images
* Screenshot folders

### Output

* Organized chapter dataset

Folder Structure:

/data

/manhwa_name

/chapter_001

/chapter_002

/chapter_003

---

## Module 2: Story Understanding

### Purpose

Extract story events from chapter images.

### Input

Chapter images

### Processing

Vision AI:

* Character detection
* Dialogue understanding
* Event extraction
* Fight detection
* Plot twist detection

### Output

JSON Summary

Example

{
"characters": [],
"events": [],
"twists": [],
"important_scenes": []
}

---

## Module 3: Viral Scene Extractor

### Purpose

Select only the most engaging moment.

### Rules

Prioritize:

* Power reveals
* Betrayals
* Revenge
* Major fights
* Rank upgrades
* Hidden abilities

Avoid:

* Long conversations
* Exposition
* World building

### Output

Top scene candidates

---

## Module 4: Hindi Script Generator

### Input

Scene summary

### Output

30–60 second Hindi narration

### Script Rules

* Simple Hindi
* Dramatic tone
* Short sentences
* Cliffhanger ending
* No complex vocabulary

### Template

HOOK

CONFLICT

POWER REVEAL

CLIFFHANGER

---

## Module 5: Voice Generation

### Input

Hindi script

### Output

MP3 narration

### Stage 1

Open-source TTS

### Stage 2

Premium voice services

Target:

Natural Hindi male voice

---

## Module 6: Subtitle Generator

### Input

Voice file

### Output

SRT subtitles

### Requirements

* Word-level timing
* Hindi support
* Burn-in support

---

## Module 7: Video Generator

### Input

* Chapter images
* Voice narration
* Subtitles

### Effects

* Zoom
* Pan
* Motion movement
* Scene transitions

### Output

1080x1920 vertical video

Target Length:

30–60 seconds

---

## Module 8: Thumbnail Generator

Optional for Shorts.

Focus should remain on content quality.

---

## Module 9: Upload Automation

### Metadata Generation

Generate:

* Title
* Description
* Tags

### Upload Queue

Videos should be uploaded automatically or queued for manual approval.

---

# Technology Stack

## Core Language

Python

### Reasons

* Existing familiarity
* AI ecosystem
* Video processing libraries

---

## AI Layer

Gemini API

Tasks:

* Story extraction
* Summaries
* Script generation

---

## Video Processing

FFmpeg

MoviePy

Tasks:

* Video assembly
* Subtitle rendering
* Compression

---

## Speech

Stage 1

Open-source TTS

Stage 2

Premium TTS

---

## Automation

n8n (Optional)

OR

Custom Python Scheduler

---

# Folder Structure

project/

data/

scripts/

generated/

audio/

subtitles/

videos/

thumbnails/

logs/

config/

main.py

---

# Analytics System

Track every Short.

## Database Fields

* Video ID
* Upload Date
* Manhwa Name
* Genre
* Views
* Likes
* Comments
* Watch Percentage
* Subscribers Gained

---

# Optimization Strategy

After 30 Days

Analyze:

### Best Genre

Example:

Dungeon System

Average Views: 15,000

Murim

Average Views: 2,000

Focus only on winner.

---

# Growth Targets

## Month 1

* 60–90 Shorts
* 100 Subscribers

## Month 2

* 150–180 Shorts Total
* 500 Subscribers

## Month 3

* 250+ Shorts Total
* First viral Short

---

# Risks

## Copyright

High Risk

Mitigation:

* Heavy editing
* Commentary
* Transformative narration
* Avoid direct chapter reposting

---

## Reused Content

Medium Risk

Mitigation:

* Add analysis
* Add opinions
* Add storytelling

---

## Automation Quality

Risk:

AI-generated scripts may become repetitive.

Mitigation:

* Regular prompt updates
* Quality review system
* Performance-based optimization

---

# MVP Goal

Build Version 1 with:

1. Chapter Images Input
2. Gemini Summary
3. Hindi Script Generation
4. Voice Generation
5. FFmpeg Video Creation

Ignore:

* Website
* Cloud Infrastructure
* Complex Analytics

Focus only on:

Input → Short → Upload

---

# Long-Term Vision

Create a fully automated Hindi Manhwa content engine capable of:

* 2–3 Shorts/day
* Minimal manual effort
* Data-driven niche selection
* Scalable content production
* Expansion into long-form recaps after validation

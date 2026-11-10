---
name: motion-design
description: >
  Applies motion design principles to create emotionally-driven, technically sound animations and transitions.
  Provides timing, easing, choreography, and Disney animation principles adapted for UI and video generation.
  Use when creating animations, transitions, micro-interactions, Ken Burns effects, card slide-ins, subtitle reveals,
  or any motion work. Works with Python/FFmpeg, CSS, Framer Motion, GSAP, Lottie, or any animation system.
license: MIT
metadata:
  author: LottieFiles & Antigravity
  version: "1.0.0"
---

# Motion Design Skill (Video Creator Agent Guide)

## When to Apply

Use this guide when:
- Creating video animations (card entrances, Ken Burns zoom, typewriter subtitles, lower-thirds)
- Designing video transitions and micro-animations
- Choreographing multi-element sequences (background + card + text)
- Establishing brand motion identity for news reels and social videos

**Decision Tree:**
1. Does it serve a functional purpose (readability, sync)? → Strict timing rules for legibility & audio sync
2. Does it express brand personality? → Select a Motion Personality archetype (e.g., Premium for news)
3. Does it guide viewer attention? → Disney principles (staging, secondary action) + choreography
4. Is this a multi-element scene? → 1/3 Rule + staggered entrance delays

---

## 8-Step Quick Reference Checklist

Before designing or coding any animation:

1. **Emotional target:** (e.g., authority, elegance, urgency for daily news digest)
2. **Motion Personality:** Premium (news broadcast), Energetic (sports/viral), Corporate (analytics), Playful
3. **Primary property:** Position (slide-in), Scale (Ken Burns zoom), Opacity (fade)
4. **Duration:** 
   - Card entrance: 350–500ms
   - Subtitle reveal: synchronized with spoken word duration
   - Background zoom: entire clip duration (slow, steady 1.00x → 1.04x)
5. **Easing family:**
   - Entrances: Decelerate (`ease-out` / cubic-bezier)
   - Exits: Accelerate (`ease-in`)
   - Continuous (Ken Burns): Smooth linear or subtle ease-in-out
6. **Hero element:** Apply visual staging (card/headline is hero, background is ambient)
7. **Secondary + ambient layers:**
   - Primary: News headline / narration
   - Secondary: News card slide-in and drop shadow / border
   - Ambient: Slow Ken Burns background zoom
8. **1/3 rule:** Avoid animating all elements at the same instant; stagger card entrance by 100-200ms after scene starts.

---

## Three Pillars

Every animation must satisfy three pillars:

| Pillar | Question | Video Engine Application |
|---|---|---|
| **Emotional Intent** | What should the viewer feel? | Reliable, professional news broadcast feel |
| **Visual Narrative** | What's the micro-story? | Scene starts → Card slides into focus → Text reads with voice → Smooth transition |
| **Motion Craft** | How do we make it believable? | Smooth deceleration curves, no harsh linear stops, natural physics |

**Three motion layers:**
- **Primary**: News image card & highlighted headline
- **Secondary**: Smooth borders, shadows, active cursor typing
- **Ambient**: Background studio ambience with gentle Ken Burns motion

---

## Motion Personality Archetypes

| Archetype | Duration | Easing | Overshoot | Best Suited For |
|---|---|---|---|---|
| **Premium** | 350-500ms | `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo) | 0% | News digests, documentaries, luxury |
| **Corporate** | 200-350ms | `cubic-bezier(0.2, 0, 0, 1)` | 0-3% | Professional reporting, explainers |
| **Energetic** | 150-250ms | `ease-out-expo` | 10-20% | Breaking news alerts, sports clips |
| **Playful** | 200-300ms | `ease-out-back` | 15% | Entertainment, social banter |

---

## FFmpeg Motion Design Equivalents

When programming animations in FFmpeg filtergraphs:

### 1. Card Slide-in from Right (Premium Ease-Out)
- Linear slide looks robotic: `x=W-(W-target)*t` ❌
- Exponential Deceleration (Ease-Out):
  `overlay=x='max(target, target+(W-target)*exp(-8*t))':y=target_y`

### 2. Ken Burns Subtle Ambient Motion
- Avoid dizzying high-speed zooms: `z='1.10-0.10*(on/N)'` ❌
- Gentle, cinematic zoom (1.00x → 1.04x):
  `zoompan=z='1.00+0.04*(on/total_frames)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=W x H:fps=FPS`

### 3. Audio & Motion Synchronization
- Ensure visual scene does not abruptly cut off before audio tails end. Always pad 0.3s breath buffer at end of segment.

# Windows Feature Request: AI-Powered Process Gatekeeper
### "Why are you opening this?" — A System That Trains Focus, Not Just Blocks Apps

---

**Submitted via:** Windows Insider Feedback Hub / Microsoft Tech Community  
**Category:** Productivity / AI Integration / Digital Wellbeing  
**Date:** March 29, 2026  
**From:** A user who built this himself because Windows doesn't have it yet 😄

---

## The One-Sentence Version

Every time you open an app, Windows asks: **"What are you trying to do right now?"**  
If you can answer clearly → you get in.  
If you can't → the AI already knows your history, and it decides for you.

---

## The Problem (Honest Version)

I build stuff on Windows all day. I also catch myself opening YouTube, WeChat, or some random game — and I genuinely cannot explain why. It just happened.

The scary part isn't the distraction. The scary part is **the absence of intention**.

You open 50 apps a day. How many of those did you *choose* to open?

---

## What I Actually Built (Proof of Concept)

I couldn't wait for Microsoft, so I wrote a Python plugin (`lan_app_habit.py`) that does this from the outside — hooking into process creation events via WMI polling.

Here's what it does:

```
[New process detected: WeChat.exe]
↓
Popup: "You're opening WeChat. Why?"
↓
User types reason (or times out in 60s)
↓
AI analyzes reason:
  - "work message" → green light, no limit
  - "bored, just scroll a bit" → 60-min soft cap, reminder at end
  - "can't stop, need to vent" → 30-min hard cap, force close
  - "...you know why" (wink emoji) → 15-min cap, force close, 
     and the popup when it closes says YOUR OWN WORDS back to you
↓
If no answer in 60s → AI checks your history for this app
  - Never recorded → close it
  - Usually high importance → let it stay
  - Usually impulsive → close it, explain why
```

The force-close popup says something like:

> *"You said 'just for a bit' — that was 15 minutes ago. I'm closing this now. You're welcome."*

It uses **your own words**. That's the point. The AI isn't lecturing you. It's reflecting you back to yourself.

---

## Why This Belongs in the OS, Not a Plugin

Right now I'm doing this from the outside. That means:

| Limitation | Reality |
|---|---|
| Process detection latency | ~2-3 second polling delay |
| No access to window focus events | Can detect launch, not active use |
| Can't intercept before app loads | App already running when popup shows |
| No system-level credibility | User can kill the plugin |

If this were **native to Windows** — built into the process scheduler, or as a Copilot+ feature — it would be:

- **Zero latency** — intercept before the process even starts
- **Trustworthy** — can't be dismissed or killed by the user
- **Context-aware** — OS knows what's on screen, what was open before, current task state
- **Cross-device** — phone opens Instagram, PC asks "wasn't you supposed to be coding?"

---

## The Deeper Idea (Why This Is More Than Parental Controls)

This isn't parental controls. Parental controls block. This system **trains**.

Every time you cross the gate — every time you explain yourself to the AI — you're doing a micro-rep of intentional thinking.

Do it 10 times a day. Do it for a month.  
You start making fewer dumb opens. Not because you're blocked. Because you've trained yourself to notice *when* you're about to make one.

**The threshold is the training.**

The goal isn't to produce obedient users. It's to produce people who know what they're doing when they sit down at a computer.

That's what I mean by "cultivating elite users" — not gifted users, just users who own their own attention.

---

## The Architecture (For the Engineers Reading This)

Here's what the system needs to know. Microsoft already has most of it:

```
Layer 1 — Process Knowledge (AI already knows this)
  "This is WeChat.exe — social messaging app"
  "This is Genshin.exe — online game with addictive loop design"
  "This is devenv.exe — Visual Studio, engineering tool"

Layer 2 — User Context (OS knows this, just not combined)
  Current active window, last 5 apps used, time of day,
  scheduled tasks/calendar events, battery/focus mode status

Layer 3 — User Intent (the missing piece — the gate)
  "Why are you opening this RIGHT NOW?"
  Cross-reference layers 1 + 2 + user's answer
  → Generate a decision: allow / limit / block / ask again

Layer 4 — Feedback Loop (the training mechanism)
  Store every reason, every outcome
  Build a personal behavioral model over time
  Surface insights: "You open YouTube 80% of the time when you say 'just a quick break'"
```

The current plugin implements layers 3 and 4 using SQLite + keyword matching + a basic semantic scoring model (`all-MiniLM-L6-v2`). It works. But it's running on a giant's shoulder with a toothpick.

---

## What I'm Asking For

Not a productivity app. Not another Screen Time clone.

A **native OS-level intent checkpoint** — one question, before every app opens:

> *"What are you here to do?"*

And an AI that takes the answer seriously.

---

## Health Guard Specifics (Real Code, Real Logic)

The health classification in my plugin:

| User says... | AI classifies as | Time limit | Force close? |
|---|---|---|---|
| "work", "coding", "learning" | `safe` | None | No |
| "relax", "quick look", "chill" | `leisure` | 60 min | Soft reminder |
| "bored", "can't stop", "just scrolling" | `impulse` | 30 min | Yes |
| *you know what* 😅 | `danger` | 15 min | Yes + your words quoted back |
| *(no answer, timeout)* | AI decides | Based on history | Maybe |

The "your words quoted back" feature is deliberate. The AI doesn't say "this is unhealthy." It says **"you said ___."** You can't argue with yourself.

---

## Closing Note

I'm a solo developer running this as a sidecar process, polling WMI every 2 seconds, hoping Windows doesn't kill my script before it catches the process.

It works. Imperfectly. But it works.

The idea is sound. The architecture is proven. What's missing is the platform.

Microsoft already has Copilot in the taskbar, Recall taking screenshots, and AI indexing your files.

You have all the pieces. You just haven't pointed them at **the moment of opening an app** yet.

That moment is worth owning.

---

*— Yuan Kaijiang, Windows user and AI hobbyist*  
*GitHub: [lan3344/lan-learns] — the full plugin source is there*  
*"I built a health gatekeeper for my own apps because I couldn't stop opening them without thinking. It helped. It should be a feature."*

---

> **P.S.** — Yes, the "打飞机" (a Chinese internet euphemism, use your imagination 😄) example in the code is real. The point stands: if your AI gatekeeper can handle *that* gracefully — asking you why, giving you 15 minutes, quoting your own words when it closes — it can handle anything. The embarrassing edge cases are where the design gets tested.


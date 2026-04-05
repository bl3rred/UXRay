\# UXRay Design Specification (PRD)



\## Brand Identity \& Vision

UXRay is a premium, developer-first UX auditing platform. It bridges the gap between automated testing and real-user experience by using Browser Use agents to simulate authentic interactions. The brand personality is \*\*technical, high-trust, and minimalist\*\*, drawing inspiration from high-end engineering tools like Vercel, Linear, and Stripe.



\---



\## Visual Language



\### 1. Color Palette (Dark Mode)

\*   \*\*Background (Primary):\*\* `#0F0F0F` (Dark Graphite/Charcoal)

\*   \*\*Surface (Panels/Cards):\*\* `#1A1A1A` with 1px hairline borders (`#2A2A2A`)

\*   \*\*Accent (Primary):\*\* `#3B82F6` (Muted Cobalt Blue) - Used for CTAs and focus states.

\*   \*\*Typography (Headlines):\*\* `#FFFFFF` (High Contrast)

\*   \*\*Typography (Body):\*\* `#A1A1AA` (Subtle Gray)

\*   \*\*Status/Severity:\*\*

&#x20;   \*   High: `#EF4444` (Muted Red)

&#x20;   \*   Medium: `#F59E0B` (Amber)

&#x20;   \*   Low: `#10B981` (Emerald)



\### 2. Typography

\*   \*\*Primary Typeface:\*\* `Geist Sans` or `Inter` (Tight tracking: `-0.02em`)

\*   \*\*Monospace:\*\* `JetBrains Mono` or `Fira Code` (For code snippets and technical logs)

\*   \*\*Hierarchy:\*\* Strong contrast between bold headlines and precise, small-scale utility text.



\### 3. Components \& UI Elements

\*   \*\*Buttons:\*\* Reduced corner radius (`6px`), subtle 1px inner border, no heavy drop shadows.

\*   \*\*Cards:\*\* Flat surfaces with subtle glassmorphism (`backdrop-filter: blur(10px)`) where depth is needed.

\*   \*\*Icons:\*\* Minimal, thin-stroke (1.5px) SVG icons. No generic "robot" or "AI" imagery.



\---



\## Landing Page Narrative (Scroll-Activated)



The landing page functions as a single-section "story" that evolves as the user scrolls, anchored by a fixed hero layout.



\### Moment 1: The Detection (Initial State)

\*   \*\*Headline:\*\* "Catch UX failures before your users do."

\*   \*\*Visual:\*\* A browser viewport showing a live audit in progress. A prominent "Issue Detected" card highlights a specific friction point (e.g., "Non-responsive checkout button").



\### Moment 2: The Solution (Transition 1)

\*   \*\*Headline:\*\* "Turn browser evidence into clear engineering fixes."

\*   \*\*Visual:\*\* The visual morphs. The issue card recedes, and a "Suggested Fix" panel takes center stage. It displays a code snippet and a likely file reference (e.g., `src/components/Checkout.tsx`).



\### Moment 3: The Insight (Transition 2)

\*   \*\*Headline:\*\* "Get structured feedback your team can act on."

\*   \*\*Visual:\*\* The UI evolves into a structured summary dashboard. A "UX Health Score" (84/100) is displayed alongside a prioritized list of findings categorized by severity and audience impact.



\---



\## Core Product Surfaces



1\.  \*\*Project Navigation (Sidebar):\*\* ChatGPT-inspired list of audit workspaces, providing quick access to recent runs and saved environments.

2\.  \*\*Live Run Viewer:\*\* The "Hero" of the app experience. A cinematic terminal-like interface where the user watches the agent interact with the DOM in real-time.

3\.  \*\*Results Dashboard:\*\* A high-density report view focused on actionable data—screenshots, severity tags, and "why it matters" explanations for founders and developers alike.


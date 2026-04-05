# UXRay PRD

## Product Summary

UXRay is a local first UX auditing platform that uses Browser Use agents to navigate websites like real users. The system tests products across multiple personas and both desktop and mobile viewports, detects where the experience breaks down, and returns actionable recommendations. When a repository is connected, UXRay also maps issues back to likely source files and generates code grounded fix suggestions.

## Core Problem

Teams can run linting, unit tests, and even end to end tests, but still ship websites that feel confusing, slow, cluttered, or inaccessible. Most tools check technical correctness, not whether a real person can understand the product, find the main action, and complete key tasks across different devices and audiences.

## Goals

- Use Browser Use as the core runtime for real browser interaction and live product evaluation
- Simulate realistic user behavior across different audiences and devices
- Detect UX, accessibility, and task completion issues using behavioral, DOM, and layout evidence
- Show users live browser runs in real time during execution
- Store projects and previous runs so users can compare improvements over time
- Generate prioritized recommendations and code grounded fixes when repo access exists

## Non Goals

- Fully autonomous deployment of fixes
- Full WCAG compliance certification
- Full support for every framework
- Production scale distributed infrastructure

## User Roles

### Developer / Builder
Creates projects, connects a URL and optionally a repo, selects personas, launches audits, reviews issues, and uses recommendations to improve the site.

### Judge / Reviewer
Watches live browser sessions, reviews issue cards, sees audience impact, and understands how the product performs for intended users.

### Browser Use Agent
Navigates the site, follows task instructions, explores flows, interacts with controls, and produces runtime evidence from real browser usage.

### Evaluation Layer
Interprets compiled issue packets from different audience perspectives and helps prioritize what matters most.

## Core Workflow

1. User creates a project with a hosted URL, GitHub repo, or both
2. System auto detects the likely site type and lets the user optionally describe the intended audience or website purpose
3. User selects one or more personas. Each persona automatically runs on both desktop and mobile viewports
4. System generates a run matrix from persona x viewport and places runs into the execution queue
5. Browser Use agents navigate the site in real time while the user can watch the sessions live
6. Playwright extracts DOM state, screenshots, timings, and layout data during the run
7. Analyzer converts evidence into issue packets
8. Optional Fetch evaluation layer reviews compiled issues from different audience perspectives
9. GPT-5.4 mini generates recommendation summaries and code grounded fix suggestions
10. Results are stored under the project so users can reopen previous runs and compare outcomes

## Queue and Execution System

UXRay enforces a strict maximum of 4 active browser sessions at any time.

A single project may create more than 4 runs, such as 3 audiences x 2 viewports = 6 runs, but any runs beyond the first 4 are queued and started automatically as active sessions finish.

### Run Statuses

- `queued`
- `running`
- `completed`
- `failed`

### Queue Rules

- Queue discipline is FIFO across pending runs
- Concurrency cap is 4 active sessions maximum across the entire app
- When one run completes, the next queued run starts automatically
- If a project creates 6 runs, 4 begin immediately and 2 start after capacity frees up

## Persona and Audience Model

Personas shape navigation priorities and task emphasis during browser runs, then reappear after issue detection to prioritize recommendations based on audience impact. They do not determine whether an issue objectively exists.

### Built In Personas

#### First Time Visitor
Primary concerns:
- clarity
- obvious next steps
- understanding the product quickly

How it influences UXRay:
- changes what the browser explores first
- frames recommendations around onboarding clarity

#### Intent Driven User
Primary concerns:
- completing a task quickly
- minimal friction

How it influences UXRay:
- emphasizes direct task completion
- prioritizes action discoverability and wasted steps

#### Trust Evaluator
Primary concerns:
- credibility
- polish
- professionalism
- transparency

How it influences UXRay:
- raises the importance of trust signals, content quality, and confidence to continue

#### Custom Audience
Derived from optional user input such as:
- website to sell my action figure collection
- portfolio for aerospace internship recruiters
- landing page for tutoring services

How it influences UXRay:
- adapts priorities and recommendation framing to a specific audience context

## Product Surfaces

### Project Sidebar
ChatGPT style left navigation with saved projects, recent runs, quick project switching, and persistent history.

### Project Overview
Project metadata, source links, latest score, run history, and buttons to launch new audits.

### Live Run Viewer
Embedded browser view or streamed session, current URL, current action, run progress, and live issue stream.

### Results Dashboard
Overall score, issue cards, screenshots, audience impact summary, viewport differences, recommendations, and likely code areas.

### Compare View
Before vs after comparisons and mobile vs desktop differences across completed runs.

## Issue Detection System

UXRay detects issues by combining multiple evidence sources instead of relying on a single model opinion. This keeps detection grounded and lets the explanation layer stay evidence based.

### Signal Types

#### Behavioral
Examples:
- time to first action
- hesitation
- retries
- repeated scrolling
- dead clicks
- delayed feedback

Why it matters:
- shows where real users struggle or waste time

#### DOM / Structural
Examples:
- element roles
- labels
- text
- visibility
- route context
- hierarchy
- presence of key controls

Why it matters:
- helps identify what the page contains and whether important controls exist

#### Layout / Viewport
Examples:
- above fold placement
- overlap
- clipping
- off screen controls
- mobile specific layout changes

Why it matters:
- explains when something is technically present but not practically usable

#### Visual Snapshot
Examples:
- screenshots captured at load
- hesitation moments
- failure states

Why it matters:
- provides proof for the dashboard and supports human readable issue explanations

### Example Issue Classes

- CTA below fold
- dead button
- slow feedback after click
- hidden navigation
- weak form feedback
- mobile specific layout issue
- low prominence action
- obvious accessibility warning

## Issue Packet Schema

```ts
type IssuePacket = {
  issueId: string
  projectId: string
  runId: string
  route: string
  persona: string
  viewport: "desktop" | "mobile"
  issueType: string
  severity: number
  evidence: {
    timeToFindMs?: number
    scrollCount?: number
    retryCount?: number
    clickDelayMs?: number
    notes?: string[]
  }
  screenshotPath?: string
  domSnippet?: string
  confidence: number
}
```

## Fetch Agent Evaluation Architecture

Fetch is optional and sits after raw issue detection. It does not replace Browser Use. Instead, it reviews compiled issue packets from different audience perspectives and helps decide what to fix first.

### Agents

#### First Time Visitor Agent
Purpose:
- evaluate onboarding clarity and whether a new user understands how to proceed

Inputs:
- issue packet
- site type
- task
- screenshot summary

Outputs:
- audience impact
- priority
- fix direction

#### Intent Driven Agent
Purpose:
- evaluate how much the issue blocks quick task completion

Inputs:
- issue packet
- task
- viewport
- evidence

Outputs:
- audience impact
- urgency
- fix direction

#### Trust Evaluator Agent
Purpose:
- evaluate credibility, polish, and confidence impact

Inputs:
- issue packet
- screenshot summary
- site type

Outputs:
- audience impact
- trust risk
- fix direction

#### Custom Audience Agent
Purpose:
- evaluate issues using the user provided audience description

Inputs:
- issue packet
- custom audience description
- site type

Outputs:
- audience impact
- audience specific rationale
- fix direction

#### Boss Agent
Purpose:
- moderate the second round
- identify disagreement
- request one focused rebuttal if needed

Inputs:
- outputs from all audience agents

Outputs:
- discussion control
- narrowed conflicts

#### Synthesis Agent
Purpose:
- compile final audience aware recommendation brief
- prepare handoff to GPT

Inputs:
- all agent outputs plus boss summary

Outputs:
- final prioritized brief for recommendation generation

### Discussion Flow

- Round 1: each audience agent independently reviews the same issue packet
- Round 2: boss agent asks for one controlled rebuttal only if disagreement matters
- Final pass: synthesis agent compiles a ranked recommendation brief for GPT

## Code Mapping and Fix Generation

If a repository is connected, UXRay maps runtime issues back to likely source code. It combines route context, text search, component hints, and grep results, then sends only the most relevant snippets to GPT-5.4 mini.

### Steps

1. Candidate search  
   Use ripgrep against route names, visible text, headings, placeholders, classes, and labels

2. Context extraction  
   Pull nearby code windows, typically around plus or minus 50 lines around matched locations

3. Recommendation generation  
   Send issue packet plus snippets to GPT-5.4 mini

4. Optional verification  
   Re run the same flow after changes

### Outputs

- ranked list of likely files
- focused snippets for reasoning
- root cause hypothesis
- recommended fix
- optional patch snippet
- before vs after comparison

## Data Model

### Project

```ts
type Project = {
  id: string
  name: string
  sourceType: "url" | "repo" | "both"
  url?: string
  repoUrl?: string
  description?: string
  createdAt: string
}
```

### Run

```ts
type Run = {
  id: string
  projectId: string
  persona: string
  viewport: "desktop" | "mobile"
  task: string
  status: "queued" | "running" | "completed" | "failed"
  score?: number
  startedAt?: string
  completedAt?: string
}
```

### Issue

```ts
type Issue = {
  id: string
  runId: string
  issueType: string
  severity: number
  confidence: number
  screenshotPath?: string
  route?: string
}
```

### Recommendation

```ts
type Recommendation = {
  id: string
  issueId: string
  audienceSummary: string
  fixText: string
  likelyFiles: string[]
  codeSnippet?: string
}
```

### Artifact

```ts
type Artifact = {
  id: string
  runId: string
  artifactType: "screenshot" | "trace" | "log"
  path: string
  metadata?: Record<string, unknown>
}
```

## API Surface

### Projects

- `POST /projects`  
  Create a new project  
  Accepts URL, repo, and optional description

- `GET /projects`  
  List projects for sidebar display

- `GET /projects/{id}`  
  Get project details and history

### Runs

- `POST /projects/{id}/runs`  
  Create audit runs for selected personas and both viewports  
  Generates run matrix and enqueues runs

- `GET /runs/{id}`  
  Fetch detailed run state

- `GET /runs/{id}/stream`  
  Stream live run updates via WebSocket or SSE

### Issues

- `GET /issues/{id}`  
  Get issue details and recommendation

- `POST /issues/{id}/reverify`  
  Re run a flow after changes for before vs after comparison

## Dashboard Output Requirements

### Top Level Summary

- overall score from 0 to 100
- status tag such as Good, Needs Work, or Critical Issues
- primary insight as a one sentence summary of the biggest problem found

### Audience Impact Summary

Show condensed impact by audience without exposing raw agent debate.

Example:
- First time users: high friction
- Intent driven users: high task blockage
- Trust evaluators: medium concern

### Issue Cards

Each issue card should include:
- screenshot
- evidence
- why it matters
- recommended fix
- audience impact summary
- likely code areas if repo is connected

### Viewport Comparison

Show desktop vs mobile differences for the same flow.

### Likely Code Areas

When repo is connected, show likely files and focused code suggestions.

## Acceptance Criteria

- User can create a project and launch a run without writing custom test scripts
- System supports hosted URL input, optional repo input, and saved project history
- Each selected persona automatically runs on both desktop and mobile viewports
- No more than 4 browser sessions run at the same time under any condition
- User can watch active browser sessions in real time while they navigate
- Issue cards include screenshots, evidence, explanation, and recommended fixes
- If a repo is connected, at least some issues can be mapped to likely files with code suggestions
- The product story remains Browser Use first. Browser Use discovers the issues by actively interacting with websites

## Tech Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

### Backend
- FastAPI

### Browser Runtime
- Browser Use

### Instrumentation
- Playwright

### Reasoning and Recommendations
- GPT-5.4 mini

### Optional Evaluation Layer
- Fetch uAgents

### Repo Analysis
- GitPython
- ripgrep
- Python subprocess

### Persistence
- SQLite

### Artifact Storage
- local filesystem storage

### Queue
- in process queue with strict max concurrency of 4 sessions

## Monorepo Suggestion

```txt
uxray/
  apps/
    web/
    api/
  packages/
    shared/
    prompts/
    types/
  artifacts/
  temp/
  README.md
```

## Session Handoff and Context Retention

To preserve continuity across long build sessions, the repo should include a dedicated `handoff.md` file that is updated at meaningful milestones. This file is meant for humans and coding agents so future sessions can recover state quickly without re-reading the entire codebase.

### Purpose

The `handoff.md` file should:
- preserve current project state across Codex, Cursor, or other agent sessions
- summarize what is already built
- document what is currently broken or incomplete
- list the next highest priority tasks
- capture important architectural decisions and constraints
- prevent repeated re-discovery of the same context

### Required Handoff File Path

```txt
uxray/handoff.md
```

### Handoff Update Triggers

Update `handoff.md` whenever one of these happens:
- a major feature is completed
- architecture changes
- a blocker is discovered
- the queue or runtime logic changes
- data models or API contracts change
- a session ends with partially completed work
- a run pipeline step is added or removed

### Required Handoff Sections

```md
# UXRay Handoff

## Current Status
Short summary of what currently works.

## What Was Completed This Session
Bullet list of completed tasks.

## In Progress
What is partially done right now.

## Blockers
Current bugs, missing credentials, broken flows, or external blockers.

## Next Priorities
Ordered list of the next best tasks to do.

## Architecture Notes
Important decisions, tradeoffs, and constraints that future sessions must preserve.

## API / Schema Changes
Any route, payload, database, or shared type changes.

## Files Touched
List of files created or modified in the latest session.

## How To Run
Exact commands to boot frontend, backend, workers, and local test flows.

## Known Issues
Open issues that are not blockers but still matter.

## Notes For Next Session
Direct handoff instructions for the next coding session.
```

### Handoff Content Rules

- Keep it concise but specific
- Prefer facts over narrative
- Include exact file paths
- Include exact commands when relevant
- Do not store secrets in the file
- Replace stale information rather than endlessly appending
- Keep the Next Priorities section tightly ordered

### Example Handoff Template

```md
# UXRay Handoff

## Current Status
Project creation works. Run creation works. Queue exists with a hard cap of 4 concurrent sessions. Live viewer UI is scaffolded but not yet wired to real Browser Use streams.

## What Was Completed This Session
- Added project and run database models
- Implemented FIFO queue with max concurrency of 4
- Added desktop and mobile run generation
- Created initial issue packet schema

## In Progress
- Wiring Browser Use live session updates into the frontend viewer
- Connecting repo grep results into recommendation generation

## Blockers
- Need stable Browser Use session streaming implementation
- Repo boot flow still fails on some Vite projects without explicit port detection

## Next Priorities
1. Finish live run streaming to the frontend
2. Persist screenshots and run artifacts
3. Connect GPT recommendation pipeline
4. Add compare view for desktop vs mobile

## Architecture Notes
- Browser Use remains the core runtime
- Playwright handles DOM extraction and metrics
- Fetch is optional and only used after issue detection
- Never exceed 4 active sessions at once

## API / Schema Changes
- `POST /projects/{id}/runs` now expands persona x viewport into run matrix
- Added `IssuePacket` evidence fields: `timeToFindMs`, `scrollCount`, `retryCount`

## Files Touched
- `apps/api/app/routes/projects.py`
- `apps/api/app/services/queue.py`
- `apps/web/app/projects/[id]/page.tsx`
- `packages/types/src/issues.ts`

## How To Run
- Frontend: `pnpm --filter web dev`
- Backend: `uvicorn app.main:app --reload`
- Ripgrep must be installed locally
- SQLite file is stored at `apps/api/data/uxray.db`

## Known Issues
- Live viewer sometimes lags one step behind
- Mobile screenshots are not yet grouped cleanly in the UI

## Notes For Next Session
Start with queue verification, then finish live viewer wiring before touching Fetch integration.
```

### Implementation Requirement

The repository should ship with:
- a real `handoff.md` file in the repo root
- an instruction in the root `README.md` telling future sessions to read `handoff.md` first
- future coding sessions should update `handoff.md` before ending if they changed meaningful project state

## Pitch Summary

UXRay uses Browser Use agents to navigate products like real users, find where the experience breaks down across devices and audiences, and turn those findings into actionable UX and code level improvements. The Browser Use layer handles real web interaction, while the post analysis layer helps prioritize what matters most for the intended audience.

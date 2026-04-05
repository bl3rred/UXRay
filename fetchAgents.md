\# UXRay Fetch Agent Blueprint



\## What each Fetch agent does, what it needs, and where synthesis fits



Use case. UXRay is a Browser Use powered UX auditing platform that evaluates websites across multiple audiences and both desktop and mobile viewports. Browser Use agents run the website flows and collect the evidence. Fetch agents review the compiled issues from different audience perspectives, discuss priorities, and produce a final recommendation brief that is then passed to GPT for code fix generation.



\---



\## 1. Why multiple agents matter



UXRay should not frame the evaluation layer as one generic AI reviewer. To highlight Fetch well, the post-analysis workflow should use multiple specialized agents with clear boundaries and visible outputs.



Each agent should own one perspective, receive the same structured issue packet, and return a concrete opinion about audience impact, priority, and fix direction.



Browser Use remains the source of truth for what happened in the browser. Fetch agents do not detect raw issues themselves. They interpret already compiled evidence.



\---



\## 2. Human role in the loop



Role



What they do



Where they interact with the agents



Developer / Builder



Runs audits, reviews results, decides what to fix, and applies code changes.



Reviews the final synthesized recommendations and code suggestions.



Judge / Reviewer



Evaluates whether UXRay delivers useful output and whether the system clearly shows value.



Sees the live browser runs, the issue cards, and the summarized audience-aware recommendations.



Browser Use runtime



Navigates the website, executes flows, captures screenshots, and produces evidence.



Feeds the post-analysis layer with issue packets.



Fetch agents



Interpret compiled issues from different audience perspectives and debate priority.



Operate only after the issue packets are already created.



GPT code generation layer



Turns the final synthesized recommendation brief into code-level fixes and patch suggestions.



Receives the final handoff from the synthesis agent.



\---



\## 3. Recommended agent set



Agent



Primary job



Main input



Main output



First-Time Visitor Agent



Judge clarity and onboarding friction for new users



Issue packet + site type + task + screenshot summary



Audience impact, priority, fix direction



Intent-Driven Agent



Judge how much the issue blocks fast task completion



Issue packet + task + viewport + behavioral evidence



Audience impact, urgency, fix direction



Trust Evaluator Agent



Judge credibility, polish, and confidence impact



Issue packet + screenshot summary + site type



Audience impact, trust risk, fix direction



Custom Audience Agent



Judge the issue for the user’s specific intended audience



Issue packet + custom audience description + site type



Audience impact, audience-specific rationale, fix direction



Boss Agent



Moderate the second round, identify conflicts, and keep the discussion disciplined



Outputs from all audience agents



Focused rebuttal request or consensus summary



Synthesis Agent



Merge the discussion into a final recommendation brief for GPT



All audience outputs + boss summary



Final prioritized brief for code-fix generation



\---



\## 4. First-Time Visitor Agent



Purpose. Evaluates whether a brand new user can understand the product and find the next step quickly.



Why it exists. A site can be technically correct while still failing to explain itself. This agent focuses on clarity, hierarchy, and onboarding friction.



Inputs



\- compiled issue packet

\- site type

\- current task

\- screenshot summary

\- relevant behavioral metrics



How it works



It reviews the issue evidence and asks whether a new user would be confused, delayed, or unsure how to proceed. It focuses on things like hidden CTAs, unclear headings, weak navigation, and unclear flow progression.



Outputs



\- audience impact score

\- priority level

\- short explanation

\- preferred fix direction



Human relevance



This agent helps explain why something matters for onboarding and first impressions, but it does not decide whether the issue objectively exists.



Common edge cases



\- visually attractive page with unclear next action

\- too much hero space pushing the CTA down

\- navigation that assumes prior familiarity

\- jargon heavy landing pages



\---



\## 5. Intent-Driven Agent



Purpose. Evaluates whether the issue slows down or blocks users who are trying to complete a task quickly.



Why it exists. Many UX problems are not about clarity alone. They are about efficiency. This agent focuses on friction, delay, extra steps, and conversion blockage.



Inputs



\- compiled issue packet

\- task description

\- viewport

\- action trace and timing evidence

\- screenshot summary if relevant



How it works



It looks at the evidence through a task completion lens. It cares about time to action, retries, dead clicks, hidden purchase or signup paths, and delayed system feedback.



Outputs



\- audience impact score

\- urgency score

\- short explanation

\- preferred fix direction



Human relevance



This agent helps the system answer what is blocking the intended action most directly.



Common edge cases



\- CTA technically present but not found quickly

\- button clicked but no visible feedback

\- checkout path hidden on mobile

\- too many steps before the main action



\---



\## 6. Trust Evaluator Agent



Purpose. Evaluates whether an issue damages credibility, polish, or user confidence.



Why it exists. Some problems do not directly break task completion but still hurt trust. This matters for portfolios, SaaS products, ecommerce sites, and startup landing pages.



Inputs



\- compiled issue packet

\- screenshot summary

\- site type

\- behavioral evidence if relevant



How it works



It reviews whether the issue makes the product look broken, unfinished, confusing, or unreliable. It pays attention to visual polish, missing trust signals, inconsistent feedback, and weak professionalism.



Outputs



\- audience impact score

\- trust risk rating

\- short explanation

\- preferred fix direction



Human relevance



This agent helps prioritize issues that hurt confidence even when the site is technically usable.



Common edge cases



\- broken layout on mobile

\- unclear pricing or contact info

\- weak visual hierarchy

\- suspicious or unfinished interaction states



\---



\## 7. Custom Audience Agent



Purpose. Evaluates the issue against the specific audience the user describes.



Why it exists. Not every site has the same intended audience. A site selling collectibles is not judged the same way as a student portfolio or a tutoring landing page.



Inputs



\- compiled issue packet

\- custom audience description

\- site type

\- task

\- screenshot summary



How it works



It adapts the lens to the custom audience input. For example, “website to sell my action figure collection” changes what matters most. Product imagery, trust, authenticity cues, and purchase clarity may become more important.



Outputs



\- audience impact score

\- audience-specific rationale

\- priority level

\- preferred fix direction



Human relevance



This is what makes the recommendations feel tailored rather than generic.



Common edge cases



\- audience description is too vague

\- audience description conflicts with detected site type

\- niche audience where trust factors differ from normal SaaS or ecommerce expectations



\---



\## 8. Boss Agent



Purpose. Keeps the multi-agent discussion disciplined and forces a useful conclusion.



Why it exists. Without control, multi-agent systems can become repetitive, noisy, and slow. The boss agent exists to keep the conversation short and structured.



Inputs



\- all audience agent outputs from round 1

\- disagreement patterns

\- issue severity and evidence context



How it works



The boss agent compares the outputs from the audience agents and identifies whether there is meaningful disagreement. If the disagreement matters, it asks for one focused rebuttal in round 2. It should not start open-ended conversations.



Outputs



\- consensus summary

\- narrowed disagreement

\- rebuttal request if needed

\- final moderation note for synthesis



Human relevance



This is a control and coordination role, not another opinion source.



Common edge cases



\- all agents agree strongly

\- one agent overstates priority

\- custom audience conflicts with first-time user interpretation

\- debate starts drifting away from actual evidence



\---



\## 9. Synthesis Agent



Purpose. Produces the final recommendation brief that is passed to GPT for code fix generation.



Why it exists. The output shown to the user should not be a pile of agent messages. It should be a clean, actionable recommendation with prioritized rationale.



Inputs



\- all agent outputs

\- boss summary

\- original issue packet

\- site type

\- audience description if present



How it works



It merges the viewpoints into one final answer. It should preserve the strongest shared concerns, acknowledge meaningful disagreement if necessary, and produce a clean implementation-oriented handoff.



Outputs



\- final issue priority

\- merged rationale

\- recommended fix direction

\- audience impact summary

\- GPT handoff payload



Human relevance



This is the bridge between Fetch evaluation and actual implementation guidance.



Common edge cases



\- agents agree on impact but disagree on fix direction

\- high severity issue but low audience-specific relevance

\- strong custom audience concern that does not matter to general users



\---



\## 10. Two-round discussion flow



UXRay should use a controlled two-round process, not open-ended discussion.



\### Round 1

Each audience agent independently reviews the same issue packet and returns:



\- audience impact

\- priority

\- fix direction

\- short rationale



\### Round 2

The boss agent compares those outputs.



If disagreement matters, the boss agent asks for one focused rebuttal:

\- confirm consensus

\- or state the strongest objection in one concise response



Then the conversation stops.



\### Final synthesis

The synthesis agent compiles:

\- the shared priorities

\- any meaningful disagreement

\- the final audience-aware recommendation brief

\- the payload passed to GPT



This keeps the system useful without becoming noisy.



\---



\## 11. Recommended message schema



Each audience agent should return something structured like this:



```ts

type AudienceReview = {

&#x20; agentName: string

&#x20; audienceType: string

&#x20; impactScore: number

&#x20; priorityScore: number

&#x20; fixDirection: string

&#x20; rationale: string

}

````



The boss agent output should look like:



```ts

type BossReview = {

&#x20; consensusLevel: "high" | "medium" | "low"

&#x20; mainConflict?: string

&#x20; rebuttalRequest?: string

&#x20; summary: string

}

```



The synthesis agent output should look like:



```ts

type SynthesizedRecommendation = {

&#x20; finalPriority: number

&#x20; audienceImpactSummary: string

&#x20; mergedRationale: string

&#x20; recommendedFixDirection: string

&#x20; gptHandoff: string

}

```



\---



\## 12. What GPT should receive after Fetch



GPT should not receive raw chat logs. It should receive a clean synthesized payload.



Suggested handoff structure:



\* issue title

\* issue packet summary

\* strongest evidence

\* final audience impact summary

\* merged rationale

\* recommended fix direction

\* likely file candidates if repo exists

\* relevant code snippets if repo exists



This keeps code generation focused and prevents noisy prompts.



\---



\## 13. End-to-end workflow example



Browser Use detects an issue:



\* mobile CTA below fold

\* 2 scrolls required

\* 8.2 seconds before first interaction



Issue packet is created with:



\* route

\* screenshot

\* evidence metrics

\* severity

\* DOM snippet



Round 1:



\* First-Time Visitor Agent says the next step is not obvious

\* Intent-Driven Agent says this blocks fast task completion

\* Trust Evaluator Agent says the page feels less polished but not critically broken

\* Custom Audience Agent says collectible buyers may miss the purchase path and lose confidence



Boss Agent:



\* sees strong agreement that this is high priority

\* no major rebuttal needed



Synthesis Agent:



\* merges into one final brief:



&#x20; \* high priority

&#x20; \* mobile users are delayed from reaching the main action

&#x20; \* strongest fix direction is to move the CTA higher and reduce hero space



GPT then receives that brief plus repo snippets and generates code-level fix guidance.



\---



\## 14. What to show in the demo



Show that Browser Use found the problem first.



Then show that the Fetch layer interprets that issue from multiple audience perspectives.



Then show the synthesis output, not the entire internal debate.



Best demo sequence:



1\. Browser Use agent runs the site

2\. Issue appears with screenshot and evidence

3\. Audience impact summary appears

4\. Final synthesized recommendation appears

5\. GPT outputs likely code changes



This makes the value of each layer obvious:



\* Browser Use finds

\* Fetch prioritizes

\* GPT translates into implementation guidance



\---



\## 15. Implementation priority for the hackathon



Priority



Agent(s)



Reason



Must-have



First-Time Visitor Agent, Intent-Driven Agent, Synthesis Agent



These give the clearest multi-audience story without too much overhead



Should-have



Trust Evaluator Agent, Boss Agent



These improve prioritization quality and discussion control



Nice-to-have



Custom Audience Agent



This makes the product feel more tailored, but can come after the core flow works



\---



\## 16. Setup guidance for building the agents



Keep the setup narrow and controlled.



\### Step 1



Create one shared issue packet schema that every agent can read.



\### Step 2



Create one agent per audience perspective with a tightly defined role and small structured output.



\### Step 3



Create a boss agent that only moderates disagreement, not free-form discussion.



\### Step 4



Create a synthesis agent that merges the outputs and generates one final handoff for GPT.



\### Step 5



Wire the Fetch layer only after Browser Use issue generation is already stable.



\### Step 6



Show Fetch outputs in the UI as:



\* audience impact summary

\* top concern

\* fix direction



Do not show raw message logs unless needed for debugging.



\---



\## 17. Design rules for the Fetch layer



\* Browser Use remains the core runtime

\* Fetch only runs after issue detection

\* agents should not invent new issues

\* agents should stay grounded in the issue packet

\* discussion should be limited to two rounds

\* outputs should be structured, not conversational

\* synthesis should optimize for user-facing clarity

\* GPT should receive a compact handoff, not full debate history



\---



\## 18. One-line summary



UXRay uses a network of specialized Fetch agents to review Browser Use issue findings from different audience perspectives, prioritize what matters most, and produce a final implementation brief for code fix generation.




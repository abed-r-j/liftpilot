# LiftPilot: live demo runbook

Demo length: **3:30** in two parts. A 15-second click after slide 11 starts the agent. The
3:15 walk-through comes between slide 14 and slide 15. Machine: the MSI GP66 (Windows 11,
RTX 3080). Everything runs locally. The only network calls are the exchange-rate and
public-holiday feeds, and both have an offline cache.

Why the agent is started early. In the agent benchmark (`docs/RESULTS.md`, section 10) the
median time for a full campaign plan was **149 seconds**. In `artifacts/agent_eval.json` the
seven campaign plans took between 51 and 218 seconds, and the request used in this demo (budget
in BRL) took 194 seconds. A wait of that length does not fit inside a 3:30 demo. So the agent
works while slides 12 to 14 are presented, and a finished run of the same request waits in a
second browser tab as a backup.

All commands are PowerShell, run from the repository root:

```powershell
cd "C:\Users\abedr\Downloads\AI in Business and Marketing\liftpilot"
```

This runbook was checked against `src\liftpilot\app\main.py` and `src\liftpilot\cli.py`. The
timings and the two points marked "confirm in rehearsal" could not be tested while it was
written, because the app was not started. Rehearse the whole path at least twice.

## 1. Pre-flight checklist

### The evening before

| # | Check | Command or action | Expected |
|---|---|---|---|
| 1 | Trained artifacts exist | `Test-Path artifacts\x5\report.json` | `True` |
| 2 | The model is installed | `ollama list` | a line starting with `qwen3:8b` |
| 3 | Live feeds are cached | start the app once on a good connection (step 6 below), open tab 5 and run the demo request once | sidebar pill shows `LIVE`; from now on *Offline mode* has data to fall back on |
| 4 | Fallback screenshots exist | after that rehearsal run, take the six screenshots listed in section 5 and save them in `docs\presentation\fallback\` | six PNG files |
| 5 | Windows will not interrupt | Settings > System > Power: plugged in, *Best performance*; turn on *Do not disturb*; pause Windows Update for 7 days | no pop-ups, no sleep |

### 30 minutes before the talk

| # | Step | Command or action | Expected |
|---|---|---|---|
| 1 | Plug in the charger | the GPU is throttled on battery | charging icon |
| 2 | Close everything that uses the GPU or RAM | games, other browsers, Teams, Docker | Task Manager: GPU memory mostly free |
| 3 | Start Ollama | open the **Ollama** app from the Start menu (tray icon appears). If it is not installed as an app, run `ollama serve` in a second PowerShell window and leave it open | `ollama list` answers without an error |
| 4 | Warm the model | `ollama run qwen3:8b "Reply with the single word: ready"` | the word `ready`, then the prompt returns |
| 5 | Confirm it sits on the GPU | `ollama ps` | `qwen3:8b` listed, processor column shows GPU |
| 6 | Start the app | `.\.venv\Scripts\liftpilot.exe app` (same as `.\.venv\Scripts\python.exe -m liftpilot.cli app`) | the browser opens `http://localhost:8501`; leave this PowerShell window open |
| 7 | Wait for the first load | the page shows *Loading customers and models...* | six tabs appear: ① Problem, ② Customers (RFM), ③ Uplift models, ④ Optimizer, ⑤ AI agent, ⑥ Ethics & audit |
| 8 | Read the sidebar | two pills | `LIVE` (or `CACHED`) followed by `1 RUB = ... USD`; `Local model: qwen3:8b` in green |
| 9 | **Decide on the Wi-Fi now** | if the room Wi-Fi is slow or needs a login page, switch on **Offline mode (use cached live data)** in the sidebar | the pill changes to `CACHED`; nothing else changes |
| 10 | Pre-compute the two plans | tab **④ Optimizer**: wait for the plan at 2 RUB (spinner *Replaying the plan on held-out customers...*), then drag **Cost per message (RUB)** to **6.0** (click the handle, then use the arrow keys; one step is 0.1) and wait again | both plans are now cached. Leave the slider on 6.0 |
| 11 | Make the **backup run** | tab **⑤ AI agent**: open **Example requests** and choose the entry that starts with "The CEO gives us a budget of 1,000,000 BRL" (it is the third line of the list; the first line is "(type your own)"). Click **▶ Run agent** and wait for the answer. Do **not** approve | answer after two to four minutes, with the pills *language model*, *... tool calls*, *... s*, *numeric grounding .../...*. Note the time it took. This browser tab is now the **backup tab**: do not touch it again |
| 12 | Prepare the **live tab** | open a second browser tab (Ctrl+T) on `http://localhost:8501`. It is a new session, so repeat two settings: *Offline mode* as decided in step 9, and tab **④**: drag the cost to **6.0** (instant, the plan is cached). Then tab **⑤**: choose the same example so that the box **Request to the agent** shows the request. Do **not** click Run. Leave tab ⑤ in front | request visible, **▶ Run agent** button enabled |
| 13 | Screen | browser zoom **125%** (Ctrl and +), browser full screen (F11), display set to *Duplicate* | text readable from the back row |
| 14 | PowerPoint | open `docs\presentation\LiftPilot.pptx`, start the slide show on slide 1. **Alt+Tab** switches between PowerPoint and the browser; **Ctrl+Tab** switches between the live tab and the backup tab | Alt+Tab shows exactly two windows |

The app asks Ollama to keep the model loaded for 30 minutes after each call. If more than 25
minutes pass between step 11 and the talk, repeat step 4 during the previous speaker's
questions.

Do not press F5 after step 12. A reload starts a new session: the cost slider goes back to 2.0
and a finished run disappears from that browser tab.

## 2. The request to use

Tab **⑤ AI agent**, selector **Example requests**, the entry:

> The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. Plan the campaign and show the evidence.

Use the selector. Do not type on stage. This request is on slide 14. A request with almost the
same wording is one of the 13 benchmark cases, and it exercises the live exchange rate (the
budget is in reais, the data in roubles).

## 3. Click path

### Part 1: start the agent (0:15, after slide 11, before slide 12)

| Where | Click | Say |
|---|---|---|
| Alt+Tab to the browser. The live tab shows tab **⑤ AI agent** with the request in the box | click **▶ Run agent** once. Wait until the spinner *Agent is working: calling tools on the real data...* appears. Alt+Tab back to PowerPoint | "Before I explain the agent, I give it a job. This is the CEO's request, in reais. I click Run, and it works while I talk." |

From this click until the answer is on screen, **do not touch any control in the live tab**: no
slider, no toggle, no selector, no button. Changing a control makes the page run again and the
agent's answer can be lost. Clicking a tab title is safe, because all six tabs are already on
the page. (Confirm both points in rehearsal.)

Then present slides 12, 13 and 14 (1:50).

### Part 2: the walk-through (3:15, after slide 14)

Times are cumulative from the moment the browser is on screen.

| Clock | Where | Click | Say |
|---|---|---|---|
| 0:00 | Alt+Tab to the browser, tab **① Problem** | click the tab title; point at the four tiles | "This is the same system, on this laptop, on the real data. The experiment you saw: 60 percent bought with no message, 64 percent with one. The real effect is 3.3 points." |
| 0:15 | tab **② Customers (RFM)** | click the tab; point at the left of the bar chart | "The RFM segments, computed from the receipts, with the uplift measured in each. Champions, on the left, react least." |
| 0:30 | tab **③ Uplift models** | click the tab; point at the red line. Do not scroll | "The model comparison. Red is the likely-buyer model, below the random line." |
| 0:40 | tab **④ Optimizer** | click the tab. Do **not** move the slider. Point at the tile **Contact**, then the bar chart, then the yellow box | "The optimizer, set to 6 roubles a message. The plan contacts about 19 percent of the audience. At 2 roubles it was about 70 percent. The bar chart shows that contacting everyone would lose money. And the yellow box: the fairness audit flagged the age gap by itself." |
| 1:05 | tab **⑤ AI agent** | click the tab. If the spinner still turns, say the waiting script and click nothing. When the answer is there, point at the pills *tool calls* and *numeric grounding* | "The agent has finished the job I gave it. It made these tool calls, and this is the grounding score: every number in its text was checked against a tool result." |
| 1:20 | **Agent's briefing** (left) and **Verified statements (written by code from tool results)** (right) | point left, then right | "On the left, the briefing in plain English. On the right, the verified statements, written by code. The model only narrates them." |
| 1:35 | scroll past **What the agent did** to **Personalised messages (one per RFM segment)** | point at the column *Passed checks* | "One message per RFM segment, each checked by code. FreshMart is a fictional brand." |
| 1:45 | scroll to **Human checkpoint** | click in **Approver name (required)**, type your name, press Enter (the buttons stay grey until then), click **✅ Approve plan** | "Nothing has been sent. The export is locked until a named human approves. I approve." |
| 2:00 | same place, after the page refreshes | leave the slider **Random hold-out for measurement** at 0.10, click **⚡ Export audience file**, point at the green message | "Only now does the audience file exist, with a random ten percent hold-out to measure the next campaign." |
| 2:10 | tab **⑥ Ethics & audit** | click the tab; point at the chart on the right (*Share contacted by age band*) and its red *REVIEW* pill, then scroll to **Audit log (latest events)** | "Last tab. The age chart for the 6-rouble plan with its review flag, the list of controls, and the audit log. My approval was just recorded, with my name." |
| 2:30 | Alt+Tab back to PowerPoint, slide 15 | | "So the system works, and it flagged its own fairness problem. Let us look at that problem properly." |

The plan has 0:45 of reserve (2:30 used out of 3:15). It is there for the waiting script. If
the answer was ready at 1:05, use the reserve to speak more slowly, not to add steps.

What you should see on tab ④ at 6 RUB (from `docs/RESULTS.md`, section 6): **Contact** about
38 thousand customers, 19.0% of the audience; spend about 228 thousand RUB; real incremental
profit about 100 thousand RUB with an interval that includes zero; about 520 thousand RUB
better than contacting everyone; a yellow box saying that selection rates differ by age band,
lowest ÷ highest = 0.70. The app uses fewer bootstrap draws than the results sheet, so the ends
of the interval can differ a little. Read numbers from the screen, not from memory.

Tab ⑥ audits the plan set in tab ④ (6 RUB, margin 25%). That is the same cost as the agent's
plan, which is why the slider must stay on 6.0.

### Waiting script (only if the spinner still turns at 1:05; about 30 seconds)

Say it slowly. If the answer arrives, stop at the end of the current sentence.

> "The request is in reais and the data is in roubles, so the planner first converts the
> budget with a live exchange rate, then builds the plan. The model replays that plan on
> customers it never saw, audits fairness, sizes a hold-out group, picks a send date from a
> public-holiday calendar, and drafts one message per segment. It is not allowed to do
> arithmetic: every number it writes is checked against what the tools returned."

If the answer is still not there when you finish, use fallback A.

### Expected timings

| Action | Normal | Act if longer than |
|---|---|---|
| Switching tabs | under 1 s | 5 s: wait, keep talking |
| Tab ④ with the cost already on 6.0 (plan cached in pre-flight step 10) | under 1 s | |
| Tab ④, plan not cached | several seconds (*Replaying the plan on held-out customers...*) | 25 s: go on to tab ⑤ |
| Full agent plan for the demo request | 194 s in the benchmark run; median of all campaign plans 149 s; your own time from pre-flight step 11 | not finished at demo clock 1:35, after the waiting script: fallback A |
| Approve, then export | 1 to 3 s each | |

From the click after slide 11 to demo clock 1:05 there are about 190 seconds (15 + 110 of
slides + 65 of demo). With the waiting script the agent has about 220 seconds.

## 4. Fallbacks, by failure

| # | What you see | Do | Say |
|---|---|---|---|
| A | The spinner on tab ⑤ is still turning after the waiting script, or the answer is an error line | press **Ctrl+Tab** to the backup tab (pre-flight step 11). It shows the same request, finished. Continue the click path from 1:05 in that tab, including approval and export. Do not click **Run scripted planner** in the live tab while the spinner turns: the click is only handled when the running model call returns | "The live run is slow today. This is the same request, run on this laptop before the talk." |
| B | Before the talk, the sidebar pill says **Local model offline: scripted planner** (Ollama is not running) | start Ollama (pre-flight steps 3 to 5) and reload. If that fails, set tab ④ to 6.0 and click **Run scripted planner (no language model)** on tab ⑤ instead of **▶ Run agent**. It runs the same tools in a fixed order with the cost and margin set in tab ④, and produces the verified statements, the drafts (from pre-approved templates when the model is off) and the approval request. It does not read the BRL budget from the text; that changes nothing here, because at 6 RUB the plan needs far less than the budget. Do not use **▶ Run agent** in this state: it also falls back to the scripted planner, but with the default cost of 2 RUB | "The language model is not available, so I use the scripted planner. Same tools, same order, same checks. This is also what the system does by itself if the model is unavailable." |
| C | Sidebar pill says **FX unavailable**, or the plan step of the agent shows an error about the exchange rate (Wi-Fi) | this must be fixed before the agent is started: switch on **Offline mode (use cached live data)** in the sidebar. If it happens on stage, use the backup tab (A) | "The Wi-Fi is down, so I show the run made before the talk. The feeds are cached for exactly this reason: live data must never be able to break the plan." |
| D | A yellow warning says *The model's wording failed a check, so it was discarded. The verified statements are shown instead.* | nothing to fix. This is a control working. In the benchmark it happened in 1 of 13 runs | "The model's wording failed a check, so the system discarded it and shows the verified statements. You are watching a guardrail fire." |
| E | The page shows a red Streamlit error, or the browser tab is blank | do not reload. Press **Ctrl+Tab** to the backup tab and continue there (A) | "Let me switch to the second window." |
| F | The app does not come back, or the laptop freezes | Alt+Tab to the folder `docs\presentation\fallback\` and step through the six screenshots with the arrow keys, saying the same lines as the click path | "I will show you the same run recorded earlier on this machine." |
| G | The projector fails entirely | stay on your feet and give the 60-second version from `SCRIPT.md`, then go to slide 15 when the screen returns | |
| H | You are told you have one minute left during the demo | go straight to **Human checkpoint**, approve, and go to slide 17 | "The last thing to see is this: nothing leaves without a named approval." |

Terminal fallback, if the browser is the problem but the terminal works. It takes as long as a
normal agent run, two to four minutes, so start it early:

```powershell
.\.venv\Scripts\liftpilot.exe agent "The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. Plan the campaign and show the evidence." --offline
```

The command prints each tool call with its arguments, then a line `answer (llm, ...s)`, the
answer, the line `numeric grounding: .../...`, and `waiting for human approval of <plan id>`.
Add `--scripted` to skip the language model; the scripted run ignores the numbers in the
request and plans with the default cost of 2 RUB and margin of 25%. Add `--show-results` to
print each tool result.

## 5. Screenshots to take during rehearsal (fallback F)

Save as PNG in `docs\presentation\fallback\`, named so that they sort in order:

1. `1_problem.png`: tab ① with the four tiles and both charts.
2. `2_rfm.png`: tab ② bar chart and the reading under it.
3. `3_optimizer_6rub.png`: tab ④ with the cost at 6.0, the five tiles and the fairness warning.
4. `4_agent_answer.png`: tab ⑤ after the run: pills, briefing and verified statements.
5. `5_checkpoint_export.png`: tab ⑤ lower part: messages table, approval and the green export message.
6. `6_ethics_audit.png`: tab ⑥ with the age chart and the audit log showing the approval.

## 6. After the talk

Stop the app with Ctrl+C in its PowerShell window. Quit Ollama from the tray icon. The exported
audience file (`runs\<plan id>\`) and the audit log (`runs\audit.jsonl`) stay on the laptop;
they contain only data from the public dataset.

## 7. Things not to say, and things on screen not to read out

- Do not call the channel SMS. Say "a message". The source says only "a communication".
- On tab ①, the grey note under the four tiles starts with a dataset description stored in
  `artifacts\x5\report.json`. That stored text still contains the word "SMS". Do not read the
  note out. If someone points at it, say that the word is a leftover in a stored description
  and that the source does not name the channel.
- Do not say the profit is guaranteed. At 6 RUB the plan's interval includes zero; the screen shows it.
- Do not say "roubles" as a fact about the data if asked; the currency is presumed.
- Do not read the numbers on the agent screen from memory. Read them from the screen: the
  exchange rate is live, so the converted budget changes from day to day.
- Do not say the agent run takes "a few seconds". The measured median is 149 seconds.

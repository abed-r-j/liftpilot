# LiftPilot: live demo runbook

Demo length: **3:30** in two parts. A 15-second click after slide 11 starts the agent. The
3:15 walk-through comes between slide 14 and slide 15. Machine: the MSI GP66 (Windows 11,
RTX 3080). Everything runs locally. The only network calls are the exchange-rate and
public-holiday feeds, and both have an offline cache.

Why the agent is started early. A full campaign plan takes about **50 seconds on a cool
laptop** and **two minutes or more when the GPU is hot or shared**. In the agent benchmark
(`docs/RESULTS.md`, section 10) the median was **136 seconds**. In `artifacts/agent_eval.json`
the seven campaign plans took between 40 and 161 seconds: the first three, run on a cool
machine, took 40 to 59 seconds, and the later ones 136 to 161 seconds. The benchmark case
closest to the demo request (budget in BRL) took 136 seconds. A wait of that length does not
fit inside a 3:30 demo. So the agent works while slides 12 to 14 are presented, the first four
demo tabs are narrated while it finishes, and a finished run of the same request waits in a
second browser tab as a backup.

All commands are PowerShell, run from the repository root:

```powershell
cd "C:\Users\abedr\Downloads\AI in Business and Marketing\liftpilot"
```

This runbook was checked against `src\liftpilot\app\main.py`, `src\liftpilot\agent\runtime.py`
and `src\liftpilot\cli.py` after the code review fixes. The figures quoted for tab ④ were
recomputed with the app's own engine calls. What could not be tested while it was written: the
app in a browser, and anything that needs the language model. Those points are marked "confirm
in rehearsal". Rehearse the whole path at least twice, once on a cool machine and once right
after another agent run.

## 1. Speed pre-flight (do this first; it decides how long the agent takes)

The language model shares the laptop GPU with everything else on screen. The same request that
takes about 50 seconds on a cool, idle machine takes two minutes or more when the GPU is hot or
when another program holds part of its memory.

| # | Do | How | Why |
|---|---|---|---|
| 1 | Close GPU-hungry apps | Quit **Steam**, **Discord**, **Slack**, Teams, any game launcher, and every browser window with many tabs. Quit them from the tray icon too (closing the window is not enough). Keep one browser window for the demo | they hold GPU memory and wake the GPU up; part of the model then runs on the CPU |
| 2 | Plug in the charger | wall power, not a USB-C dock | the GPU is throttled on battery |
| 3 | Turn on the MSI fan boost | Cooler Boost: the fan key on the keyboard or the switch in MSI Center (find it in rehearsal). It is loud: speak up, or switch it off once the agent's answer is on screen | a hot GPU slows down; the fans at full speed keep it near the cool-machine time |
| 4 | Check the GPU is free | Task Manager > Performance > GPU: dedicated GPU memory mostly free before Ollama starts | confirms step 1 worked |
| 5 | Warm the model ten minutes before the talk | one throwaway request: `ollama run qwen3:8b "Reply with the single word: ready" --keepalive 30m` | loads the model into GPU memory, so the first tool call on stage does not pay the loading time. It is short on purpose: a full plan ten minutes before would heat the GPU again |
| 6 | Confirm it sits on the GPU | `ollama ps` | `qwen3:8b` listed, processor column `100% GPU` |

What to expect on stage: about **50 seconds** if the machine is cool, **2 minutes or more** if
it is hot (the backup run in section 2 heats it, which is why the fan boost stays on
afterwards). The plan does not depend on which of the two happens:

- the agent is started early, after slide 11, and works during slides 12 to 14;
- tabs ① to ④ are narrated before tab ⑤ is opened, which gives it another minute;
- if the answer is still not there, the backup browser tab holds a finished run (fallback A);
- if the language model is not running at all, the button **Run scripted planner (no language
  model)** runs the same tools in a fixed order and gives the same verified statements in a few
  seconds (fallback B; measured: about 3 seconds for the eight tool calls once the app is
  loaded).

One trap. If the local model is down and the typed request contains costs or a budget, as the
demo request does, **▶ Run agent** now refuses to plan. Nothing can read the figures out of the
text without the model, and planning on default costs while the request names other figures
would mislead. The briefing then reads: *"The local language model is not running, so the costs
or budget written in this request cannot be read. No plan was made. Set the assumptions with
the controls in the Optimizer tab and use the scripted planner, or start Ollama."* Do what it
says: set tab ④ and click **Run scripted planner (no language model)**.

## 2. Pre-flight checklist

### The evening before

| # | Check | Command or action | Expected |
|---|---|---|---|
| 1 | Trained artifacts exist | `Test-Path artifacts\x5\report.json` | `True` |
| 2 | The model is installed | `ollama list` | a line starting with `qwen3:8b` |
| 3 | Live feeds are cached | start the app once on a good connection (step 4 below), open tab 5 and run the demo request once | sidebar pill shows `LIVE`; from now on *Offline mode* has data to fall back on |
| 4 | Fallback screenshots exist | after that rehearsal run, take the six screenshots listed in section 6 and save them in `docs\presentation\fallback\` | six PNG files |
| 5 | Windows will not interrupt | Settings > System > Power: plugged in, *Best performance*; turn on *Do not disturb*; pause Windows Update for 7 days | no pop-ups, no sleep |

### 30 minutes before the talk

| # | Step | Command or action | Expected |
|---|---|---|---|
| 1 | Speed pre-flight, steps 1 to 4 | section 1: close GPU-hungry apps, charger, fan boost, GPU free | Task Manager: GPU memory mostly free |
| 2 | Start Ollama | open the **Ollama** app from the Start menu (tray icon appears). If it is not installed as an app, run `ollama serve` in a second PowerShell window and leave it open | `ollama list` answers without an error |
| 3 | Load the model | `ollama run qwen3:8b "Reply with the single word: ready" --keepalive 30m`, then `ollama ps` | the word `ready`; `qwen3:8b` listed on the GPU |
| 4 | Start the app | `.\.venv\Scripts\liftpilot.exe app` (same as `.\.venv\Scripts\python.exe -m liftpilot.cli app`) | the browser opens `http://localhost:8501`; leave this PowerShell window open |
| 5 | Wait for the first load | the page shows *Loading customers and models...* | six tabs appear: ① Problem, ② Customers (RFM), ③ Uplift models, ④ Optimizer, ⑤ AI agent, ⑥ Ethics & audit |
| 6 | Read the sidebar | two pills | `LIVE` (or `CACHED`) followed by `1 RUB = ... USD`; `Local model: qwen3:8b` in green. If it says `Local model offline: scripted planner`, go back to step 2 |
| 7 | **Decide on the Wi-Fi now** | if the room Wi-Fi is slow or needs a login page, switch on **Offline mode (use cached live data)** in the sidebar | the pill changes to `CACHED`; nothing else changes |
| 8 | Pre-compute the plans | tab **④ Optimizer**: wait for the plan at 2 RUB (spinner *Replaying the plan on held-out customers...*), then drag **Cost per message (RUB)** to **10.0** and wait, then back to **6.0** and wait (click the handle, then use the arrow keys; one step is 0.1). Leave **Gross margin** on 0.25, **Discount to buyers (share of basket)** on 0, **Limit the budget** unticked and the **Fair mode** switch off | the three plans are now cached. Leave the slider on 6.0. At 6.0 there is no yellow box; at 10.0 there was one |
| 9 | Make the **backup run** | tab **⑤ AI agent**: open **Example requests** and choose the entry that starts with "The CEO gives us a budget of 1,000,000 BRL" (it is the third line of the list; the first line is "(type your own)"). Click **▶ Run agent** and wait for the answer. Do **not** approve | answer after one to three minutes, with the pills *language model*, *... tool calls*, *... s*, *numeric grounding .../...*. Note the time it took. This browser tab is now the **backup tab**: do not touch it again |
| 10 | Prepare the **live tab** | open a second browser tab (Ctrl+T) on `http://localhost:8501`. It is a new session, so repeat two settings: *Offline mode* as decided in step 7, and tab **④**: drag the cost to **6.0** (instant, the plan is cached). Then tab **⑤**: choose the same example so that the box **Request to the agent** shows the request. Do **not** click Run. Leave tab ⑤ in front | request visible, **▶ Run agent** button enabled |
| 11 | Screen | browser zoom **125%** (Ctrl and +), browser full screen (F11), display set to *Duplicate* | text readable from the back row |
| 12 | PowerPoint | open `docs\presentation\LiftPilot.pptx`, start the slide show on slide 1. **Alt+Tab** switches between PowerPoint and the browser; **Ctrl+Tab** switches between the live tab and the backup tab | Alt+Tab shows exactly two windows |
| 13 | **Ten minutes before**: warm the model again | speed pre-flight step 5: the throwaway `ollama run ... --keepalive 30m` request, then `ollama ps`. Keep the fan boost on | `ready`; the model is on the GPU and the backup run's heat is gone |

The app asks Ollama to keep the model loaded for 30 minutes after each call, and the warm-up
command above asks for the same. Do not warm up with a plain `ollama run` without
`--keepalive 30m`: by default Ollama unloads a model five minutes after such a call.

Do not press F5 after step 10. A reload starts a new session: the cost slider goes back to 2.0
and a finished run disappears from that browser tab.

## 3. The request to use

Tab **⑤ AI agent**, selector **Example requests**, the entry:

> The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. Plan the campaign and show the evidence.

Use the selector. Do not type on stage. This request is on slide 14. A request with almost the
same wording is one of the 13 benchmark cases, and it exercises the live exchange rate (the
budget is in reais, the data in roubles).

Why not type a variant. The plan arguments must be traceable to the manager's words: a cost,
margin or discount that does not appear in the request is dropped and the default is used, and
a budget or its currency is never guessed (the plan is refused and the agent is told what to
clarify). A request restricted to an unknown segment or to a demographic group ("women over
60") is refused by the planner. All of this is good to show in questions, not during the timed
demo.

## 4. Click path

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
| 0:00 | Alt+Tab to the browser, tab **① Problem** | click the tab title; point at the four tiles (**Customers**, **Bought WITHOUT a message**, **Bought WITH a message**, **Real effect of the message**) | "This is the same system, on this laptop, on the real data. The experiment you saw: 60 percent bought with no message, 64 percent with one. The real effect is 3.3 points." |
| 0:15 | tab **② Customers (RFM)** | click the tab; point at the left of the bar chart | "The RFM segments, computed from the receipts, with the uplift measured in each. Champions, on the left, react least." |
| 0:30 | tab **③ Uplift models** | click the tab; point at the red line. Do not scroll | "The model comparison. Red is the likely-buyer model, below the random line." |
| 0:40 | tab **④ Optimizer** | click the tab. Do **not** move the slider. Point at the tile **Contact**, then the bar chart. Under the **Fair mode** switch there is no yellow box: point at that empty space | "The optimizer, set to 6 roubles a message. The plan contacts about 19 percent of the audience. At 2 roubles it was about 70 percent. The bar chart shows that contacting everyone would lose money. And no fairness warning here: at 6 roubles the audit passes." |
| 1:05 | tab **⑤ AI agent** | click the tab. If the spinner still turns, say the waiting script and click nothing. When the answer is there, point at the pills *tool calls* and *numeric grounding* | "The agent has finished the job I gave it. It made these tool calls, and this is the grounding score: every number in its text was checked against a tool result." |
| 1:20 | **Agent's briefing** (left column) and **Verified statements (written by code from tool results)** (right column) | point left, then right | "On the left, the briefing in plain English. On the right, the verified statements, written by code. The model only narrates them." |
| 1:35 | scroll past **What the agent did** to **Personalised messages (one per RFM segment)** | point at the column *Passed checks* | "One message per RFM segment, each checked by code. FreshMart is a fictional brand." |
| 1:45 | scroll to **Human checkpoint** | click in **Approver name (required)**, type your name, press Enter (the buttons stay grey until then), click **✅ Approve plan** | "Nothing has been sent. The export is locked until a named human approves. I approve." |
| 2:00 | same place, after the page refreshes | leave the slider **Random hold-out for measurement** at 0.10, click **⚡ Export audience file**, point at the green message | "Only now does the audience file exist, with a random ten percent hold-out to measure the next campaign." |
| 2:10 | tab **⑥ Ethics & audit** | click the tab; point at the chart on the right (*Share contacted by age band*) and the green *OK* pill under it, then scroll to **Audit log (latest events)** | "Last tab. The age audit of the 6-rouble plan, marked OK, then the list of controls, and the audit log. My approval was just recorded, with my name." |
| 2:30 | Alt+Tab back to PowerPoint, slide 15 | | "So the system works, and it audits its own fairness. Let us look at that audit properly." |

The plan has 0:45 of reserve (2:30 used out of 3:15). It is there for the waiting script. If
the answer was ready at 1:05, use the reserve to speak more slowly, not to add steps.

What you should see on tab ④ at 6 RUB (recomputed with the app's own calls; the same figures
are in `docs/RESULTS.md`, section 6):

- **Contact** 38,113, with "19.0% of audience" under it; **Leave alone** 162,010;
- **Spend** about 228 thousand RUB; **Real incremental profit** 99,838 RUB;
- **vs contacting everyone** about 522 thousand RUB, with "spend saved 972,403" under it;
- in the grey note: 95% interval for profit −114,276 to 299,621 RUB, which includes zero, and
  probability that profit is positive 83%;
- **no yellow box**. The fairness audit of this plan gives 0.82 for age (lowest 65+, highest
  35-44) and 0.95 for gender, both above the 0.80 line.

Read numbers from the screen, not from memory.

Two things on that tab that are new and that you do not use in the timed demo:

- **Limit the budget** (fourth column). Ticking it shows a currency selector and a **Budget**
  box. For a budget in BRL, USD or EUR a caption under the box gives the converted amount, for
  example "= ... RUB (live rate, date)" or "(cached rate, date)". If no rate is available, a
  red message says that the budget limit is NOT applied.
- The expander **Why is this one customer contacted, or not?** at the bottom. It has a
  **Customer id** selector and shows **Decision**, **Estimated uplift**, **Break-even uplift**
  and **Expected profit if contacted** for that customer.

Tab ⑥ audits the plan set in tab ④ (6 RUB, margin 25%), always with fair mode off. That is the
same cost as the agent's plan, which is why the slider must stay on 6.0. Under the age chart
the line reads "lowest ÷ highest rate = 0.82 (flag under 0.80)". The chart has a bar "under 18"
at 0.0%: minors are never contacted, and that band and "unknown" are left out of the ratio.

If someone asks to see a flag (questions only, after the export). Go to tab ④ and drag **Cost
per message (RUB)** to **10.0** (cached in pre-flight step 8). A yellow box appears under the
Fair mode switch: "Fairness audit: selection rates differ by age band (lowest ÷ highest = 0.57;
lowest: 18-24, highest: 35-44). Flagged for human review; see the Ethics tab." Tab ⑥ then shows
the red *REVIEW* pill. At 10 RUB the plan contacts 4.6% of the audience. Switching **Fair
mode** on at 6.0 also raises the yellow box (ratio 0.58): that is the negative result on
slide 15. That plan is not cached, so it takes several seconds.

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
| Tab ④ with the cost already on 6.0 (plan cached in pre-flight step 8) | under 1 s | |
| Tab ④, plan not cached | several seconds (*Replaying the plan on held-out customers...*) | 25 s: go on to tab ⑤ |
| Full agent plan for the demo request | about 50 s on a cool machine; 136 s in the benchmark run of this request (also the median of all campaign plans); slowest campaign plan in the benchmark 161 s; your own time from pre-flight step 9 | not finished at demo clock 1:35, after the waiting script: fallback A |
| Scripted planner, model off | about 3 s | |
| Approve, then export | 1 to 3 s each | |

From the click after slide 11 to demo clock 1:05 there are about 185 seconds (10 left of the
start slot + 110 of slides + 65 of demo). With the waiting script the agent has about 215
seconds. That covers every campaign plan in the benchmark, including the hot-machine ones.

## 5. Fallbacks, by failure

| # | What you see | Do | Say |
|---|---|---|---|
| A | The spinner on tab ⑤ is still turning after the waiting script, or the answer is an error line | press **Ctrl+Tab** to the backup tab (pre-flight step 9). It shows the same request, finished. Continue the click path from 1:05 in that tab, including approval and export. Do not click **Run scripted planner (no language model)** in the live tab while the spinner turns: the click is only handled when the running model call returns | "The live run is slow today. This is the same request, run on this laptop before the talk." |
| B | The sidebar pill says **Local model offline: scripted planner** (Ollama is not running), or after **▶ Run agent** the briefing says *"The local language model is not running, so the costs or budget written in this request cannot be read. No plan was made. ..."* | before the talk: start Ollama (pre-flight steps 2 and 3) and reload. On stage, or if that fails: check that tab ④ is on 6.0 and margin 0.25, then on tab ⑤ click **Run scripted planner (no language model)**. It runs the same tools in a fixed order with the cost, margin and discount set in tab ④, and in about 3 seconds gives the same verified statements, the drafts (from pre-approved templates when the model is off) and the approval request. Then continue the click path from 1:05: approval and export work the same. The first pill reads *scripted planner* instead of *language model*. The scripted planner does not read the BRL budget from the text; that changes nothing here, because at 6 RUB the plan needs far less than the budget. Do **not** click **▶ Run agent** in this state: the demo request names a cost and a budget, so the agent refuses to plan | "The language model is not available, so I use the scripted planner. Same tools, same order, same checks, and the same verified statements. Without the model the system refuses to guess the costs in my sentence, so I set them with the sliders." |
| C | Sidebar pill says **FX unavailable**, or the plan step of the agent shows an error about the exchange rate (Wi-Fi) | this must be fixed before the agent is started: switch on **Offline mode (use cached live data)** in the sidebar. If it happens on stage, use the backup tab (A) | "The Wi-Fi is down, so I show the run made before the talk. The feeds are cached for exactly this reason: live data must never be able to break the plan." |
| D | A yellow warning says *The model's wording failed a check, so it was discarded. The verified statements are shown instead.* | nothing to fix. This is a control working. In the benchmark it happened in 1 of 13 runs | "The model's wording failed a check, so the system discarded it and shows the verified statements. You are watching a guardrail fire." |
| E | The first pill of the answer reads *scripted planner* although you clicked **▶ Run agent**, and the first verified statement says "2 RUB per message" | the model stopped answering before the first tool call, so the run fell back to the scripted planner with default costs. Do not approve that plan. Use the backup tab (A), or click **Run scripted planner (no language model)**, which uses the 6.0 set in tab ④ | "The model dropped out, so this plan used default costs. Let me show the run with the right cost." |
| F | The page shows a red Streamlit error, or the browser tab is blank | do not reload. Press **Ctrl+Tab** to the backup tab and continue there (A) | "Let me switch to the second window." |
| G | The app does not come back, or the laptop freezes | Alt+Tab to the folder `docs\presentation\fallback\` and step through the six screenshots with the arrow keys, saying the same lines as the click path | "I will show you the same run recorded earlier on this machine." |
| H | The projector fails entirely | stay on your feet and give the 60-second version from `SCRIPT.md`, then go to slide 15 when the screen returns | |
| I | You are told you have one minute left during the demo | go straight to **Human checkpoint**, approve, and go to slide 17 | "The last thing to see is this: nothing leaves without a named approval." |

If the language model is running, **Run scripted planner (no language model)** still asks it
to write the eight message drafts, so it takes longer than 3 seconds (time it in rehearsal).
The plan, the evidence, the fairness audit and the verified statements never need the model.

Terminal fallback, if the browser is the problem but the terminal works. It takes as long as a
normal agent run, one to three minutes, so start it early:

```powershell
.\.venv\Scripts\liftpilot.exe agent "The CEO gives us a budget of 1,000,000 BRL. A message costs 6 RUB, margin 25%. Plan the campaign and show the evidence." --offline
```

The command prints each tool call with its arguments, then a line `answer (llm, ...s)`, the
answer, the line `numeric grounding: .../...`, and `waiting for human approval of <plan id>`.
If Ollama is not running, this command prints the same refusal as the app and makes no plan.
Add `--scripted` to skip the language model; the scripted run ignores the numbers in the
request and plans with the default cost of 2 RUB and margin of 25%, so say so if you show it.
Add `--show-results` to print each tool result.

## 6. Screenshots to take during rehearsal (fallback G)

Save as PNG in `docs\presentation\fallback\`, named so that they sort in order:

1. `1_problem.png`: tab ① with the four tiles and both charts.
2. `2_rfm.png`: tab ② bar chart and the reading under it.
3. `3_optimizer_6rub.png`: tab ④ with the cost at 6.0, the Fair mode switch, the five tiles and no fairness warning.
4. `4_agent_answer.png`: tab ⑤ after the run: pills, **Agent's briefing** and **Verified statements**.
5. `5_checkpoint_export.png`: tab ⑤ lower part: messages table, approval and the green export message.
6. `6_ethics_audit.png`: tab ⑥ with the age chart, its *OK* pill and the audit log showing the approval.

## 7. After the talk

Stop the app with Ctrl+C in its PowerShell window. Quit Ollama from the tray icon. Switch the
fan boost off. The exported audience file (`runs\<plan id>\`) and the audit log
(`runs\audit.jsonl`) stay on the laptop; they contain only data from the public dataset.

## 8. Things not to say, and things on screen not to read out

- Do not call the channel SMS. Say "a message". The source says only "a communication", and
  the grey note under the four tiles on tab ① says "a marketing communication".
- Do not say the profit is guaranteed. At 6 RUB the plan's interval includes zero; the screen shows it.
- Do not say "roubles" as a fact about the data if asked; the currency is presumed.
- Do not say the 6-rouble plan was flagged for fairness. It was not: its age ratio is 0.82 and
  the flag starts under 0.80. The flag appears at 10 RUB (0.57), and with fair mode on at 6 RUB
  (0.58).
- Do not read the numbers on the agent screen from memory. Read them from the screen: the
  exchange rate is live, so the converted budget changes from day to day, and the send date
  depends on the day of the talk.
- If someone notices that the profit interval on tab ④ (−114,276 to 299,621) is not the one in
  the agent's verified statements (−99,289 to 296,175): it is the same plan and the same
  estimate, 99,838 RUB. Both are bootstrap intervals computed with a different number of
  random draws, and both are on the results sheet (sections 6 and 7).
- Do not say the agent run takes "a few seconds". It takes about 50 seconds on a cool machine
  and the measured median is 136 seconds. Only the scripted planner takes a few seconds.

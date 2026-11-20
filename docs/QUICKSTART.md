# LiftPilot: how to start it and use it

A short version for everyday use. The full stage procedure, with timings and fallbacks, is in
[presentation/DEMO_RUNBOOK.md](presentation/DEMO_RUNBOOK.md).

## Start it (every time)

1. **Start Ollama.** Open the **Ollama** app from the Start menu and wait for its tray icon.
   This is the local language model the agent uses.
2. **Open PowerShell in the project folder.**

   ```powershell
   cd "C:\Users\abedr\Downloads\AI in Business and Marketing\liftpilot"
   ```

3. **Start the dashboard.** Leave this window open while you use the app.

   ```powershell
   .\.venv\Scripts\python.exe -m liftpilot.cli app
   ```

4. **Wait for the browser.** It opens `http://localhost:8501` by itself. The first load shows
   *Loading customers and models...* for up to a minute, then six tabs appear.
5. **Check the sidebar.** You want a green pill `Local model: qwen3:8b` and a pill starting
   with `LIVE` (or `CACHED`). If it says `Local model offline: scripted planner`, Ollama is not
   running: go back to step 1 and reload the page.

To stop: press **Ctrl+C** in the PowerShell window, then quit Ollama from its tray icon.

## Use it

| Tab | What to do | What you see |
|---|---|---|
| ① Problem | nothing, just read | the experiment: who bought with and without a message, and the real effect |
| ② Customers (RFM) | nothing, just read | the RFM segments and the measured uplift in each |
| ③ Uplift models | nothing, just read | the model comparison (Qini curves) |
| ④ Optimizer | drag **Cost per message**, **Gross margin**, **Discount to buyers**; tick **Limit the budget**; switch **Fair mode** | who to contact, the spend, the real incremental profit and its interval; a yellow box if the fairness audit flags the plan |
| ⑤ AI agent | pick a line under **Example requests** (or type a request), click **▶ Run agent**, wait one to three minutes | the briefing, the verified statements, the tool calls, one message per segment |
| ⑤ AI agent, lower part | read the block **Before you approve: CHECK**, then type a name in **Approver name (required)**, press Enter, click **✅ Approve plan**, then **⚡ Export audience file** | first the CHECK block: five lines written by code from this run's tool results (Claims, Hunt the source, Evidence and numbers, Cross-check, Keep a human sign-off). After approval, a slider **Random hold-out for measurement** that starts at the share designed in the run. After export, the audience file is written to `runs\<plan id>\` |
| ⑥ Ethics & audit | nothing, just read | the age and gender audit of the plan set in tab ④, the controls, the audit log |

Things to know:

- The CHECK block sits above the approver name field while the plan is not yet approved. It
  shows how many numbers the briefing states and how many were matched to a tool result or to
  a number in the request, the tool calls and whether their results are in the audit log, the
  replay profit with its 95% interval, the model's expectation beside the replay with the
  fairness ratios against the 0.80 line, and that nothing is exported until a named person
  approves. It adds no button and no extra click. It is there to be read.
- If the block says "Steps not done in this run", the agent did not finish the checklist for
  that plan. Do not approve it. Run the request again. The Approve button is still shown, so
  this is your decision, not something the screen stops.
- After approval, the slider **Random hold-out for measurement** starts at the share designed
  in the run, the same share the verified statements give, and a caption under it says so. If
  the run designed no hold-out it starts at 10%. Move it only if you mean to export a share
  different from the one in the briefing.

- After you click **▶ Run agent**, do not touch any slider, switch or selector until the answer
  is on screen. Clicking a tab title is safe.
- Do not press F5. A reload resets the sliders and removes a finished agent run.
- If the agent is slow, close Steam, Discord and Slack (from the tray too) and plug in the
  charger. They share the graphics card with the language model.
- No internet: switch on **Offline mode (use cached live data)** in the sidebar.
- No language model: set the costs in tab ④, then click **Run scripted planner (no language
  model)** in tab ⑤. It gives the same plan and the same verified statements in a few seconds.

## If something does not start

| Symptom | Fix |
|---|---|
| `liftpilot.exe` is blocked by Windows | use the command in step 3 above (`python.exe -m liftpilot.cli app`), not `liftpilot.exe` |
| "Port 8501 is already in use" | the app is already running: open `http://localhost:8501`, or close the other PowerShell window |
| The sidebar says the model is offline | start Ollama, then run `ollama list` and check that a line starts with `qwen3:8b` |
| The page stays on *Loading customers and models...* for several minutes | check that `artifacts\x5\report.json` exists; if not, run `.\.venv\Scripts\python.exe -m liftpilot.cli train` |

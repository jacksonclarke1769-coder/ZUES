# Getting Started with ZEUS

This guide is written for someone who is new to the project. You do not need to be a
programmer to follow it. Take each step in order.

---

## What you are setting up

ZEUS is an automated trading bot. Once configured, it watches the NQ Nasdaq-100 futures
market, decides when to trade based on a fixed (certified) strategy, and sends orders to
Tradovate automatically. You will set up the code on your local computer so you can:

- Read the dashboard and monitor live trades
- Run research tools and backtests
- Use Claude Code to ask questions and make approved changes
- Understand exactly what the system is doing and why

**You will NOT be starting the live bot during this guide.** The live bot requires separate
operator approval and a specific launch checklist. This guide gets you to the point where
everything is installed and you can read the code safely.

---

## Step 1 — Install Git

Git is the tool that downloads the code from GitHub and tracks changes.

**Mac:**
Open Terminal (press Cmd+Space, type "Terminal", press Enter) and run:
```bash
git --version
```
If you see a version number, Git is already installed. If a dialog appears asking you to
install "command line developer tools", click Install and wait for it to finish.

**Windows:**
Download Git from https://git-scm.com/download/win and install it with default options.
After installing, open "Git Bash" from the Start menu — use that instead of Command Prompt
for the rest of this guide.

---

## Step 2 — Install Python 3.11 or higher

Python is the programming language ZEUS is written in.

1. Go to https://www.python.org/downloads/
2. Download **Python 3.11** (or any newer version — 3.12, 3.13 are fine).
3. Run the installer. On Windows, tick "Add Python to PATH" before clicking Install.
4. Verify in Terminal / Git Bash:
   ```bash
   python3 --version
   ```
   You should see something like `Python 3.11.x` or `Python 3.12.x`.

---

## Step 3 — Clone the repository

"Cloning" means downloading a copy of the code to your computer.

In Terminal / Git Bash, navigate to the folder where you want to keep the code (your Desktop
or a "Projects" folder works fine), then run:

```bash
git clone <repo-url> nq-liq-bot
cd nq-liq-bot
```

Replace `<repo-url>` with the actual GitHub URL (ask the operator for this if you don't have it).

You now have a folder called `nq-liq-bot` with all the code inside.

---

## Step 4 — Install Claude Code

Claude Code is Anthropic's AI assistant that knows how to read and explain this codebase.
It is the main way you will interact with ZEUS safely.

Install it with:
```bash
npm install -g @anthropic-ai/claude-code
```

If you see "command not found: npm", you need to install Node.js first:
1. Go to https://nodejs.org/
2. Download the LTS version and install it.
3. Then run the command above again.

Verify Claude Code is installed:
```bash
claude --version
```

---

## Step 5 — Open a Terminal in the project folder

All commands in this guide must be run **inside the `nq-liq-bot` folder**. Make sure your
Terminal is there:

```bash
# Check you are in the right place
pwd
# Should print something ending in /nq-liq-bot
ls AGENTS.md
# Should print: AGENTS.md
```

If `ls AGENTS.md` shows an error, you are in the wrong folder. Use `cd nq-liq-bot` to get there.

---

## Step 6 — Run the safe setup script

This script installs everything ZEUS needs. It is safe to run — it does not start the bot,
send any orders, or connect to any broker.

```bash
./setup-zeus.sh
```

The script will:
1. Check your Python version
2. Create a virtual environment (an isolated Python install for this project)
3. Install all Python packages from `requirements.txt`
4. Create a `.env` file from `.env.example` (only if `.env` does not already exist)
5. Verify that required folders and contract files are in place
6. Run a quick smoke test

If the script exits with an error, read the error message carefully — it will tell you
what is missing and how to fix it.

---

## Step 7 — Fill in your credentials

The setup script created a file called `.env` in the project root. This file holds your
private credentials (Tradovate login, API key, etc.). Open it in any text editor and fill
in the values marked as `YOUR_VALUE_HERE`.

**Important rules about `.env`:**
- Never commit it to Git. It is already listed in `.gitignore` so this should happen
  automatically, but double-check before any `git add` command.
- Never share it, paste it into Claude Code, or put it anywhere online.
- Never print its contents to the Terminal.

---

## Step 8 — Activate the virtual environment

Every time you open a new Terminal session to work on ZEUS, run:

```bash
source .venv/bin/activate
```

Your prompt will change to show `(.venv)` at the start, confirming the virtual environment
is active. All Python commands (`python3`, `pytest`, etc.) will then use the project's
isolated packages.

---

## Step 9 — Run the full test suite

Check that everything is set up correctly:

```bash
python3 -m pytest -q
```

This runs about 720 tests and takes around 30 seconds. The expected output ends with:
```
N passed, 1 skipped in Xs
```
(where N is the number of tests — it should be 0 failed).

If you see failures, read the error message. Most setup issues show up here as import
errors or missing files. Do not proceed until the test suite is green.

---

## Step 10 — Start Claude Code

```bash
claude
```

This opens the Claude Code assistant. It will read `AGENTS.md`, `CLAUDE.md`, and
`SUBAGENTS.md` automatically, so it understands the project's rules.

You can ask it questions like:
- "Explain what Profile A does."
- "What does Exit#3 mean?"
- "Show me the safety gates in auto_safety.py."
- "What does the D1c filter do?"

See [`docs/CLAUDE_CODE_GUIDE.md`](CLAUDE_CODE_GUIDE.md) for safe prompts and what to avoid.

---

## How to know setup worked

You are set up correctly when ALL of these are true:

- [ ] `python3 -m pytest -q` completes with 0 failed
- [ ] `python3 tools_doc_consistency.py` prints `✓ docs consistent`
- [ ] `.env` exists and has your credentials filled in
- [ ] `claude` opens Claude Code without errors
- [ ] You can ask Claude Code "What is the current locked machine?" and get the correct answer
      (Profile A · Exit#3 · D1c · $1,200 budget · B OFF · mm OFF)

---

## What comes next

Once setup is complete, the operator will walk you through the pre-launch checklist in
`README.md` before the bot goes live. Do not attempt to start the live bot on your own.

Good questions to explore with Claude Code before going live:
- "Walk me through what happens when auto_live.py gets a Profile A signal."
- "What does go-live-recert.sh check before it starts the bot?"
- "What safety systems stop the bot if something goes wrong?"

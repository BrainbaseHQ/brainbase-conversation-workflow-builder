<div align="center">

# Brainbase Conversation Workflow Builder

**Describe a phone call in plain language. Get a validated voice agent workflow.**

By [Brainbase](https://github.com/BrainbaseHQ)

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)

</div>

Brainbase Conversation Workflow Builder is a skill for Claude, Codex, Cursor and other coding agents that writes and edits the workflow JSON behind AI voice call agents. Tell your coding agent what the call should do, answer a few questions, and paste the result into your voice agent.

It's built on failures seen in real calls: greetings that leave personal details on a voicemail, endings that ask questions after the call has hung up, and retry loops that stall.

## Install

> [!NOTE]
> Brainbase Conversation Workflow Builder is a standalone skill for now, not a plugin, so there's no marketplace install yet.

### Let your agent install it

Paste the prompt for your tool. If your agent can read web pages, pasting just the link to this repo and asking it to install the skill also works.

**Claude Code**

```text
Install the skill from https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder into ~/.claude/skills. Follow the "Instructions for agents" section of its README.

This skill contains instructions on how to turn a description of a phone call into
workflow JSON for an AI voice agent, or edit a workflow you already have. It asks
a few questions (at most 5 for a new workflow), writes the JSON, checks it with an
offline validator, and explains the finished call in plain language.
```

**Codex**

```text
Install the skill from https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder into ~/.agents/skills. Follow the "Instructions for agents" section of its README.

This skill contains instructions on how to turn a description of a phone call into
workflow JSON for an AI voice agent, or edit a workflow you already have. It asks
a few questions (at most 5 for a new workflow), writes the JSON, checks it with an
offline validator, and explains the finished call in plain language.
```

**Cursor**

```text
Install the skill from https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder into ~/.cursor/skills. Follow the "Instructions for agents" section of its README.

This skill contains instructions on how to turn a description of a phone call into
workflow JSON for an AI voice agent, or edit a workflow you already have. It asks
a few questions (at most 5 for a new workflow), writes the JSON, checks it with an
offline validator, and explains the finished call in plain language.
```

**Claude (web and desktop chat)**

Here you upload the skill yourself, and this prompt walks you through it:

```text
Help me install the skill from https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder. Follow the "Instructions for agents" section of its README.

This skill contains instructions on how to turn a description of a phone call into
workflow JSON for an AI voice agent, or edit a workflow you already have. It asks
a few questions (at most 5 for a new workflow), writes the JSON, checks it with an
offline validator, and explains the finished call in plain language.
```

**Other agents**

This works in any agent listed under [Other agents](#other-agents) below:

```text
Install the skill from https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder into this tool's personal skills folder. Follow the "Instructions for agents" section of its README.

This skill contains instructions on how to turn a description of a phone call into
workflow JSON for an AI voice agent, or edit a workflow you already have. It asks
a few questions (at most 5 for a new workflow), writes the JSON, checks it with an
offline validator, and explains the finished call in plain language.
```

### Claude (web and desktop)

1. **[Download `brainbase-conversation-workflow-builder.zip`](https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder/releases/latest/download/brainbase-conversation-workflow-builder.zip).** Keep it zipped.
2. In Claude, go to **[Customize > Skills](https://claude.ai/customize/skills)**.
3. Click **+**, then **Create skill**, then **Upload a skill**.
4. Select the zip. Make sure the skill is toggled on in your skills list.

> [!IMPORTANT]
> Use the download link above, not GitHub's green **Code > Download ZIP** button. That button names the folder `brainbase-conversation-workflow-builder-main`, and Claude expects the folder name to match the skill name.

Skills need code execution, which you can turn on in **Settings > Capabilities**. On Team and Enterprise plans, an owner may need to allow skills first. See [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude).

### Claude Code

Download the same zip, then unzip it into your personal skills folder:

```bash
mkdir -p ~/.claude/skills && unzip brainbase-conversation-workflow-builder.zip -d ~/.claude/skills/
```

Run `/brainbase-conversation-workflow-builder` to use it directly. If you just created `~/.claude/skills`, run `/reload-skills` first.

### Codex

Download the same zip, then unzip it into your personal skills folder:

```bash
mkdir -p ~/.agents/skills && unzip brainbase-conversation-workflow-builder.zip -d ~/.agents/skills/
```

In the Codex CLI or IDE extension, type `$brainbase-conversation-workflow-builder` to use it directly, or run `/skills` to find it. If it doesn't appear, restart Codex. See [Codex skills](https://developers.openai.com/codex/skills).

### Cursor

Download the same zip, then unzip it into your personal skills folder:

```bash
mkdir -p ~/.cursor/skills && unzip brainbase-conversation-workflow-builder.zip -d ~/.cursor/skills/
```

In Agent chat, type `/` and search for `brainbase-conversation-workflow-builder` to use it directly. See [Cursor skills](https://cursor.com/docs/skills).

### Other agents

Download the same zip, then unzip it into your tool's personal skills folder. For example, for Gemini CLI:

```bash
mkdir -p ~/.gemini/skills && unzip brainbase-conversation-workflow-builder.zip -d ~/.gemini/skills/
```

| Tool | Skills folder | How to use it |
| --- | --- | --- |
| [Gemini CLI](https://geminicli.com/docs/cli/skills/) | `~/.gemini/skills` | Loads when your request matches, after you approve it. Run `/skills reload` if you installed it during a session. |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills) | `~/.copilot/skills` | Put `/brainbase-conversation-workflow-builder` in your prompt. Run `/skills reload` if you installed it during a session. |
| [OpenCode](https://opencode.ai/docs/skills/) | `~/.config/opencode/skills` | Loads when your request matches. |
| [Cline](https://docs.cline.bot/features/skills) | `~/.cline/skills` | Type `/brainbase-conversation-workflow-builder`, or let it load when your request matches. |
| [Factory Droid](https://docs.factory.com/cli/configuration/skills) | `~/.factory/skills` | Type `/brainbase-conversation-workflow-builder`, or let it load when your request matches. |
| [Amp](https://ampcode.com/docs/customize/skills) | `~/.config/agents/skills` | Loads when your request matches. |
| [Devin Desktop](https://docs.devin.ai/desktop/cascade/skills) | `~/.config/devin/skills` | Type `/brainbase-conversation-workflow-builder`, or let it load when your request matches. |

Using something else? If your tool supports `SKILL.md` skills, check its docs for the personal skills folder. Many also read `~/.agents/skills`.

### Updating

Download the latest zip and install it again the same way. If Claude won't accept the upload, delete the old copy first. For the unzip installs, delete the old `brainbase-conversation-workflow-builder` folder first, or ask your agent to reinstall the skill.

## Instructions for agents

If someone gave you this repo's link and asked you to install the skill, follow these steps.

1. **Pick the skills folder for the tool you're running in.** If you can't tell, ask.

   | Tool | Skills folder |
   | --- | --- |
   | Claude Code | `~/.claude/skills` |
   | Codex | `~/.agents/skills` |
   | Cursor | `~/.cursor/skills` |
   | Gemini CLI | `~/.gemini/skills` |
   | GitHub Copilot CLI | `~/.copilot/skills` |
   | OpenCode | `~/.config/opencode/skills` |
   | Cline | `~/.cline/skills` |
   | Factory Droid | `~/.factory/skills` |
   | Amp | `~/.config/agents/skills` |
   | Devin Desktop | `~/.config/devin/skills` |

   If your tool isn't listed, use the personal skills folder from its docs. If you can't confirm one, ask.

   If you're Claude in a web or desktop chat and can't write to the person's skills, don't try to install it. Give them the [download link](https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder/releases/latest/download/brainbase-conversation-workflow-builder.zip) and the upload steps from the "Claude (web and desktop)" section above, then stop.

2. **Check for an existing copy.** If `brainbase-conversation-workflow-builder` is already in that folder, ask before replacing it. If they decline, stop. Don't delete anything yet; step 3 replaces the old copy only after the new one has downloaded and been checked.

3. **Download the release zip and install it.** Set `SKILLS_DIR` to the folder from step 1. Use this zip rather than cloning the repo, so that only the skill's files are installed. On Windows, use the PowerShell equivalents, and keep the same order.

   ```bash
   (
     set -e
     SKILLS_DIR="$HOME/.claude/skills"  # replace .claude/skills with your tool's folder from step 1
     mkdir -p "$SKILLS_DIR"
     TMP_DIR="$(mktemp -d "$SKILLS_DIR/.brainbase-conversation-workflow-builder.XXXXXX")"
     trap 'rm -rf "$TMP_DIR"' EXIT
     curl -fsSL "https://github.com/BrainbaseHQ/brainbase-conversation-workflow-builder/releases/latest/download/brainbase-conversation-workflow-builder.zip" -o "$TMP_DIR/skill.zip"
     unzip -q "$TMP_DIR/skill.zip" -d "$TMP_DIR"
     test -f "$TMP_DIR/brainbase-conversation-workflow-builder/SKILL.md"
     rm -rf "$SKILLS_DIR/brainbase-conversation-workflow-builder"
     mv "$TMP_DIR/brainbase-conversation-workflow-builder" "$SKILLS_DIR/"
   )
   ```

   If this fails, tell the person what went wrong; any existing copy is still in place. If your sandbox blocks the download or the write, give them these commands to run themselves.

4. **Confirm the install.** Check that `brainbase-conversation-workflow-builder/SKILL.md` exists in the skills folder.

5. **Report back.** Tell them where you installed it and how to use it, using the section above for their tool. If the skill doesn't appear, they may need to restart the tool. Don't change anything else on their machine.

## Usage

Ask for a call in your own words. Your agent picks up the skill on its own:

```text
Build an outbound call that confirms tomorrow's dental appointments. Check the
patient's birth year before sharing any details, and offer a callback if it's a
bad time. Send the results to our webhook.
```

To change a workflow you already have, paste its JSON and describe the change:

```text
Here's our workflow: <paste JSON>
Before ending the call, ask callers who decline for the reason.
```

### What you get

| Section | What's in it |
| --- | --- |
| **Assumptions** | Any defaults the agent chose instead of asking |
| **Workflow JSON** | The workflow to paste into your agent |
| **What it does** or **What changed** | The call in plain language, greeting to goodbye |
| **What to provide** | The information each call needs, plus anything to plug in before going live |
| **Safeguards** | The protections built in, such as an identity check or honest AI disclosure |
| **Heads-up** | Anything that needs your attention, such as problems already in a workflow you're editing |

## How it works

**Creating a workflow**

1. The agent fills in what your request already says and asks at most 5 questions about the rest, each with a suggested default. Say "just build it" to skip them.
2. It sketches the call, checking that every realistic answer has somewhere to go and that every path ends the call.
3. It writes the JSON and runs the validator until there are no errors.
4. It reviews the design for what the validator can't check, such as what a real caller might say at each step.

**Editing a workflow**

The agent makes the smallest change that works. It keeps your existing ids and wording, and reports problems it finds under Heads-up instead of fixing them without asking. A diff script confirms that only the intended parts changed.

> [!NOTE]
> Passing validation means the workflow should save. It doesn't prove the conversation works, so place test calls before going live.

## What's inside

| Path | Purpose |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The instructions your agent follows |
| [`references/intake.md`](references/intake.md) | What to ask, and how answers map to the workflow |
| [`references/schema.md`](references/schema.md) | Every node type, field and graph rule |
| [`references/routing-context-code.md`](references/routing-context-code.md) | Routing, code steps and which variables are visible where |
| [`references/authoring-gotchas.md`](references/authoring-gotchas.md) | Call design, voice prompts and known production failures |
| [`references/editing.md`](references/editing.md) | Rules for changing an existing workflow |
| [`examples/appointment_confirmation.json`](examples/appointment_confirmation.json) | A complete outbound example |
| [`scripts/validate_workflow.py`](scripts/validate_workflow.py) | Offline validator (Python 3, standard library only) |
| [`scripts/diff_workflows.py`](scripts/diff_workflows.py) | Compares two versions of a workflow |

You can also run the scripts yourself:

```bash
python3 scripts/validate_workflow.py --add-positions workflow.json
```

```bash
python3 scripts/diff_workflows.py before.json after.json
```

Maintained by [Brainbase](https://github.com/BrainbaseHQ). Released under the [MIT License](LICENSE).

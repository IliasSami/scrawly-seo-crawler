# Scrawly desktop: install, update and troubleshoot

Scrawly is a free desktop app for macOS, Windows and Linux. Audits run on your own
computer, there's no account to create, and the app keeps itself up to date.

---

## 1. Install

### The quick way (recommended)

**macOS or Linux** (open Terminal):

```bash
curl -fsSL https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.sh | bash
```

**Windows** (open PowerShell):

```powershell
irm https://raw.githubusercontent.com/IliasSami/scrawly-seo-crawler/main/install.ps1 | iex
```

The installer:

1. checks for **git** and **Python 3.11+**, and installs them where it safely can
   (Homebrew on macOS, winget on Windows) or tells you the exact command to run;
2. downloads Scrawly into a `Scrawly` folder in your home folder
   (set `SCRAWLY_HOME` to choose another place);
3. creates Scrawly's own private Python environment and installs the crawler browser
   (about 150 MB, once);
4. adds Scrawly to your apps: **Applications** (macOS), **Start Menu and Desktop**
   (Windows), or your **app menu** (Linux).

Running the same command again updates an existing install.

### By hand

You need **Python 3.11 or newer** and **git**. Release copies include the interface
prebuilt, so **Node.js is not needed**.

```bash
git clone https://github.com/IliasSami/scrawly-seo-crawler.git Scrawly
cd Scrawly
python3 scripts/install.py        # Windows: py scripts\install.py
```

| If you're missing | Get it |
|---|---|
| Python 3.11+ | [python.org/downloads](https://www.python.org/downloads/), `brew install python@3.12` (macOS), `winget install Python.Python.3.12` (Windows), `sudo apt install python3.12 python3.12-venv` (Ubuntu) |
| git | [git-scm.com](https://git-scm.com/downloads), `xcode-select --install` (macOS), `winget install Git.Git` (Windows), `sudo apt install git` (Ubuntu) |

## 2. Open Scrawly

- **macOS:** open **Scrawly** from Launchpad, Spotlight or `~/Applications`
  (or double-click `Scrawly.command` in the Scrawly folder).
- **Windows:** open **Scrawly** from the Start Menu or the Desktop shortcut
  (or double-click `Scrawly.bat`).
- **Linux:** open **Scrawly** from your app menu (or run `./scrawly.sh`).

A Scrawly window opens and you're ready. Click the Scrawly logo, paste any web address,
and start an audit. When it finishes, the **Reports** tab opens the report in your browser
or saves it as a PDF (you choose where).

## 3. Updates

Every time Scrawly opens it checks GitHub for a new version. When there is one, it updates
itself, refreshes its components and restarts. Updates only install once the project's
automated tests have passed for that version.

- Turn automatic updates off: set `SCRAWLY_AUTO_UPDATE=0` (in a `.env` file in the Scrawly
  folder, or in your environment).
- If you changed files in the Scrawly folder yourself, automatic updates pause; run
  `git pull` in the folder to update by hand.

Scrawly also **repairs itself** if a system Python upgrade breaks its private environment
(common after `brew upgrade` on macOS): the next launch rebuilds it automatically.

## 4. Where your data lives

Your audits, settings and reports stay on your computer:

| System | Folder |
|---|---|
| macOS | `~/Library/Application Support/Scrawly` |
| Windows | `%APPDATA%\Scrawly` |
| Linux | `~/.local/share/scrawly` |

The launch log (`scrawly.log`) is in the same folder; attach it when reporting a problem.
To keep data elsewhere (for example a portable drive), set `SCRAWLY_DATA_DIR`.

## 5. Optional settings

Scrawly works with no configuration. Optional extras:

- **AI provider** (for written titles, descriptions and fix suggestions): in the app under
  **Settings**. Bring your own key (Anthropic or any OpenAI-compatible service).
- **Google Search Console and GA4**: in the app under **Settings, Integrations** (the panel
  walks you through the one-time Google setup).
- **PageSpeed Insights** (Core Web Vitals): add a free
  [PageSpeed API key](https://developers.google.com/speed/docs/insights/v5/get-started)
  as `PAGESPEED_API_KEY` in a `.env` file in the Scrawly folder.

For `.env`, copy [`.env.example`](../.env.example) to `.env` and fill in only what you need;
Scrawly reads it at launch.

## 6. Linux notes

The installer adds a Qt-based window component inside Scrawly's own environment, so no
system packages are usually needed. If the window still doesn't open:

```bash
# Ubuntu / Debian: libraries the Qt window and the crawler browser rely on
sudo apt install libxkbcommon-x11-0 libxcb-cursor0 libnss3 libgbm1
```

## 7. Troubleshooting

| Problem | What to do |
|---|---|
| "backend not installed" | Run the installer again: `python3 scripts/install.py` in the Scrawly folder. |
| The window doesn't open (Linux) | See Linux notes above. |
| A PDF won't save | The first PDF may download a browser component; check your connection and try again. Scrawly also fetches it in the background at launch. |
| "Scrawly's engine isn't responding" | Close and reopen Scrawly. If it persists, check `scrawly.log` (section 4). |
| An update didn't apply | You may have local changes in the folder: run `git status`, then `git pull`. |

Still stuck? Send a note from the app (speech-bubble icon in the left bar) or
[open an issue](https://github.com/IliasSami/scrawly-seo-crawler/issues) with your
operating system and `scrawly.log`.

## 8. Remove Scrawly

1. Delete the Scrawly folder (by default `Scrawly` in your home folder).
2. Remove the app entry: `~/Applications/Scrawly.app` (macOS), the Start Menu and Desktop
   shortcuts (Windows), or `~/.local/share/applications/scrawly.desktop` (Linux).
3. To also delete your audits, remove the data folder from section 4.

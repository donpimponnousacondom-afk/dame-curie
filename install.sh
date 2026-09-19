#!/usr/bin/env bash
set -euo pipefail

if [ -t 1 ]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=''; GREEN=''; YELLOW=''; RED=''; RESET=''
fi

step() { printf '\n%s==>%s %s\n' "$BOLD" "$RESET" "$*"; }
ok() { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$*"; }
fail() { printf '  %s✗%s %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
case "$SCRIPT_PATH" in
  */*)
    if SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" 2>/dev/null && pwd -P)"; then
      :
    else
      SCRIPT_DIR="$(pwd -P)"
    fi
    ;;
  *) SCRIPT_DIR="$(pwd -P)" ;;
esac

INSTALL_DIR="${DAME_CURIE_INSTALL_DIR:-$HOME/dame-curie}"
REPO_URL="${DAME_CURIE_REPO_URL:-}"
BRANCH="${DAME_CURIE_BRANCH:-main}"
RECONFIGURE=0
LOCAL_MODE=0
NO_EXTRAS=0
NONINTERACTIVE="${DAME_CURIE_NONINTERACTIVE:-0}"
SKIP_SYSTEM_DEPS="${DAME_CURIE_SKIP_SYSTEM_DEPS:-0}"
TTY=""
OS_FAMILY=""
PYTHON_BIN=""

usage() {
  cat <<'EOF'
dame-curie installer

Usage:
  bash install.sh [options]

Options:
  --help              Show this help.
  --reconfigure       Run the configuration wizard even when .env exists.
  --no-extras         Do not install optional Python/system extras.
  --non-interactive   Read all answers from environment variables.
  --dir <path>        Install/update dame-curie in this directory.
  --local             Configure the current checkout instead of cloning/updating.

Useful environment variables:
  DAME_CURIE_INSTALL_DIR, DAME_CURIE_REPO_URL (required to clone), DAME_CURIE_BRANCH,
  DAME_CURIE_NONINTERACTIVE=1, DAME_CURIE_SKIP_SYSTEM_DEPS=1,
  DISCORD_TOKEN, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_API_KEY,
  DAME_CURIE_OWNER_IDS, DAME_CURIE_INSTALL_EXTRAS=yes|no
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --reconfigure) RECONFIGURE=1 ;;
    --no-extras) NO_EXTRAS=1; DAME_CURIE_INSTALL_EXTRAS=no ;;
    --non-interactive) NONINTERACTIVE=1 ;;
    --dir) shift; [ "$#" -gt 0 ] || fail "--dir requires a path"; INSTALL_DIR="$1" ;;
    --local) LOCAL_MODE=1; INSTALL_DIR="$SCRIPT_DIR"; SKIP_SYSTEM_DEPS="${DAME_CURIE_SKIP_SYSTEM_DEPS:-1}" ;;
    *) fail "unknown option: $1 (try --help)" ;;
  esac
  shift
done

if [ -r /dev/tty ] && [ -w /dev/tty ]; then
  TTY=/dev/tty
elif [ "$NONINTERACTIVE" != "1" ]; then
  NONINTERACTIVE=1
  warn "No controlling TTY is available; switching to non-interactive mode."
  warn "Set DISCORD_TOKEN, OPENAI_BASE_URL, OPENAI_MODEL, and other DAME_CURIE_* variables, then re-run with --reconfigure if needed."
fi

prompt() {
  prompt_text=$1
  default_value=${2:-}
  answer=""
  if [ "$NONINTERACTIVE" = "1" ]; then
    printf '%s' "$default_value"
    return 0
  fi
  if [ -n "$default_value" ]; then
    printf '  %s [%s]: ' "$prompt_text" "$default_value" > "$TTY"
  else
    printf '  %s: ' "$prompt_text" > "$TTY"
  fi
  IFS= read -r answer < "$TTY" || answer=""
  if [ -n "$answer" ]; then printf '%s' "$answer"; else printf '%s' "$default_value"; fi
}

prompt_secret() {
  prompt_text=$1
  default_value=${2:-}
  answer=""
  if [ "$NONINTERACTIVE" = "1" ] || [ -z "${TTY:-}" ]; then
    printf '%s' "$default_value"
    return 0
  fi
  if [ -n "$default_value" ]; then
    printf '  %s [press Enter to keep existing/default]: ' "$prompt_text" > "$TTY"
  else
    printf '  %s: ' "$prompt_text" > "$TTY"
  fi
  IFS= read -r -s answer < "$TTY" || answer=""
  printf '\n' > "$TTY"
  if [ -n "$answer" ]; then printf '%s' "$answer"; else printf '%s' "$default_value"; fi
}

yes_no() {
  prompt_text=$1
  default_value=${2:-no}
  env_value=${3:-}
  if [ -n "$env_value" ]; then
    case "$env_value" in yes|YES|Yes|y|Y|1|true|TRUE|on|ON) printf 'yes'; return 0 ;; no|NO|No|n|N|0|false|FALSE|off|OFF) printf 'no'; return 0 ;; esac
  fi
  if [ "$NONINTERACTIVE" = "1" ]; then
    printf '%s' "$default_value"
    return 0
  fi
  while :; do
    answer=$(prompt "$prompt_text" "$default_value")
    case "$answer" in yes|YES|Yes|y|Y) printf 'yes'; return 0 ;; no|NO|No|n|N) printf 'no'; return 0 ;; *) warn "Please answer yes or no." ;; esac
  done
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    if ! command -v sudo >/dev/null 2>&1; then
      fail "sudo is required to install system packages as a non-root user. Install the packages manually or set DAME_CURIE_SKIP_SYSTEM_DEPS=1."
    fi
    warn "Using sudo to install system packages needed by dame-curie. You may be prompted for your password."
    sudo "$@"
  fi
}

detect_os() {
  if command -v apt-get >/dev/null 2>&1; then OS_FAMILY=apt; return; fi
  if command -v dnf >/dev/null 2>&1; then OS_FAMILY=dnf; return; fi
  if command -v pacman >/dev/null 2>&1; then OS_FAMILY=pacman; return; fi
  if [ "$(uname -s 2>/dev/null || printf unknown)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then OS_FAMILY=brew; return; fi
    fail "macOS detected but Homebrew is missing. Install Homebrew plus: git curl python@3.14."
  fi
  cat >&2 <<EOF
Unsupported OS/package manager.
Install these manually, then re-run with DAME_CURIE_SKIP_SYSTEM_DEPS=1:
  Required: git curl Python 3.14 with venv and pip
  Optional extras: ffmpeg, libopus/opus, libsodium, espeak-ng, nodejs
  Deployment: separately provisioned private rootless Docker engine for the service account
EOF
  exit 1
}

install_core_system_deps() {
  [ "$SKIP_SYSTEM_DEPS" = "1" ] && { warn "Skipping system package installation (DAME_CURIE_SKIP_SYSTEM_DEPS=1)."; return; }
  detect_os
  step "Installing required system packages"
  case "$OS_FAMILY" in
    apt) run_as_root apt-get update; run_as_root apt-get install -y git curl ca-certificates python3 python3-venv python3-pip ;;
    dnf) run_as_root dnf install -y git curl ca-certificates python3 python3-pip ;;
    pacman) run_as_root pacman -Sy --needed --noconfirm git curl ca-certificates python python-pip ;;
    brew) brew install git curl python ;;
  esac
}

install_extra_system_deps() {
  [ "$SKIP_SYSTEM_DEPS" = "1" ] && { warn "Skipping optional system packages (DAME_CURIE_SKIP_SYSTEM_DEPS=1)."; return; }
  [ -n "$OS_FAMILY" ] || detect_os
  step "Installing optional system packages"
  case "$OS_FAMILY" in
    apt) run_as_root apt-get update; run_as_root apt-get install -y ffmpeg libopus0 libsodium-dev espeak-ng nodejs ;;
    dnf)
      run_as_root dnf install -y opus libsodium-devel espeak-ng nodejs
      run_as_root dnf install -y ffmpeg || warn "ffmpeg not in default dnf repos (enable RPM Fusion for voice support)."
      ;;
    pacman) run_as_root pacman -Sy --needed --noconfirm ffmpeg opus libsodium espeak-ng nodejs ;;
    brew) brew install ffmpeg opus libsodium espeak-ng node ;;
  esac
}

verify_python() {
  for candidate in python3.14 python3; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 14) else 1)
PY
    then
      PYTHON_BIN="$candidate"
      ok "$("$PYTHON_BIN" -V)"
      return 0
    fi
  done
  fail "Python 3.14 with venv and pip is required; install it as a separate interpreter instead of replacing the system Python."
}

clone_or_update() {
  step "Getting dame-curie"
  if [ "$LOCAL_MODE" = "1" ]; then
    [ -f "$INSTALL_DIR/bot.py" ] || fail "--local must be run from a dame-curie checkout."
    cd "$INSTALL_DIR"
    ok "using local checkout at $INSTALL_DIR"
    return
  fi
  if [ -z "$REPO_URL" ]; then
    fail "DAME_CURIE_REPO_URL must name the source repository to clone; this installer has no implicit upstream default."
  fi
  if [ ! -e "$INSTALL_DIR" ]; then
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    ok "cloned $REPO_URL ($BRANCH) to $INSTALL_DIR"
  elif [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    if git pull --ff-only; then
      ok "updated existing checkout"
    else
      warn "git pull --ff-only failed; continuing without overwriting local changes."
    fi
  else
    fail "$INSTALL_DIR exists but is not a git repository. Move it aside or choose --dir <path>."
  fi
  cd "$INSTALL_DIR"
}

set_env_value() {
  SET_ENV_VALUE="$2" ./.venv/bin/python scripts/set_env.py .env "$1"
}

copy_env_if_needed() {
  if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    ok "created .env from .env.example"
  fi
}

install_python_deps() {
  step "Installing Python dependencies"
  if [ ! -d .venv ]; then
    "$PYTHON_BIN" -m venv .venv || fail "Could not create .venv. Ensure the selected 3.14 interpreter provides venv."
    ok "created .venv"
  fi
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  ok "core Python dependencies installed"

  printf '  Optional extras unlock: web search (ddgs), YouTube (yt-dlp), voice/VC (PyNaCl + opus), TTS (gTTS/espeak), and video/audio helpers (ffmpeg/node).\n'
  extras_default=no
  [ "$NO_EXTRAS" = "1" ] && extras_default=no
  extras=$(yes_no "Install optional extras too?" "$extras_default" "${DAME_CURIE_INSTALL_EXTRAS:-}")
  if [ "$extras" = "yes" ]; then
    install_extra_system_deps
    ./.venv/bin/python -m pip install --quiet -r requirements-optional.txt
    ./.venv/bin/python -m pip install --quiet --force-reinstall --no-deps 'discord.py-self>=2.0.0'
    ok "optional Python extras installed"
  else
    ok "optional extras skipped"
  fi
}

configure_env() {
  step "Configuring dame-curie"
  if [ -f .env ] && [ "$RECONFIGURE" != "1" ]; then
    ok ".env already exists — leaving it unchanged (use --reconfigure to edit it)"
    return
  fi
  if [ -f .env ] && [ "$RECONFIGURE" = "1" ] && [ "$NONINTERACTIVE" != "1" ]; then
    keep=$(yes_no ".env exists. Update it with the wizard?" "yes" "")
    [ "$keep" = "yes" ] || { ok "kept existing .env"; return; }
  fi
  copy_env_if_needed

  printf '\n%sStep 1/4: Discord user token%s\n' "$BOLD" "$RESET"
  printf '  This is a self-bot user token. In a browser, open Discord, DevTools, Network, select a discord.com/api request, and copy the authorization header. You can also inspect Application/Local Storage. This may violate Discord ToS.\n'
  token=$(prompt_secret "Discord token (blank to skip)" "${DISCORD_TOKEN:-}")
  if [ -n "$token" ]; then set_env_value DISCORD_TOKEN "$token"; ok "Discord token saved"; else warn "DISCORD_TOKEN left blank; the bot cannot start until you edit .env."; fi

  printf '\n%sStep 2/4: LLM provider%s\n' "$BOLD" "$RESET"
  base_default="${OPENAI_BASE_URL:-}"
  model_default="${OPENAI_MODEL:-}"
  api_key_default="${OPENAI_API_KEY:-}"
  printf '  OPENAI_* selects your remote OpenAI-compatible endpoint, not an official OpenAI account or service. No endpoint or model is assumed.\n'
  base=$(prompt "Remote OpenAI-compatible base URL" "$base_default")
  model=$(prompt "Model name" "$model_default")
  key=$(prompt_secret "Endpoint API key (blank if no bearer is required)" "$api_key_default")
  set_env_value OPENAI_BASE_URL "$base"
  if [ -n "$model" ]; then set_env_value OPENAI_MODEL "$model"; else warn "OPENAI_MODEL left blank; set it before starting dame-curie."; fi
  set_env_value OPENAI_API_KEY "$key"

  printf '\n%sStep 3/4: Owner Discord user ID(s)%s\n' "$BOLD" "$RESET"
  printf '  Enable Discord Developer Mode, right-click yourself, and choose Copy User ID. Use commas for multiple owners.\n'
  owner=$(prompt "Owner ID(s), optional" "${DAME_CURIE_OWNER_IDS:-}")
  if [ -n "$owner" ]; then
    set_env_value DAME_CURIE_OWNER_IDS "$owner"
  else
    warn "DAME_CURIE_OWNER_IDS left blank; admin commands will be denied."
  fi

  printf '\n%sStep 4/4: Optional background loops%s\n' "$BOLD" "$RESET"
  printf '  Autonomy and REM spend LLM tokens on timers, so the safe default is off.\n'
  autonomy=$(yes_no "Enable autonomy background actions?" "no" "${ENABLE_AUTONOMY:-}")
  rem=$(yes_no "Enable REM memory consolidation?" "no" "${ENABLE_REM:-}")
  if [ "$autonomy" = "yes" ]; then
    set_env_value ENABLE_AUTONOMY true
  else
    set_env_value ENABLE_AUTONOMY false
  fi
  if [ "$rem" = "yes" ]; then
    set_env_value ENABLE_REM true
  else
    set_env_value ENABLE_REM false
  fi
}

banner_and_confirm() {
  printf '%sdame-curie installer%s\n' "$BOLD" "$RESET"
  printf 'dame-curie is a Discord self-bot backed by any OpenAI-compatible LLM. This installer fetches the app, installs dependencies, creates a virtualenv in .venv, and walks you through configuration.\n\n'
  printf '%sWarning:%s dame-curie uses discord.py-self/self_bot=True. Self-bots may violate Discord Terms of Service and can put your account at risk.\n' "$YELLOW" "$RESET"
  if [ "$NONINTERACTIVE" != "1" ]; then
    answer=$(prompt "Type I UNDERSTAND to continue" "")
    [ "$answer" = "I UNDERSTAND" ] || fail "confirmation not received"
  else
    warn "Non-interactive mode: continuing after printing the self-bot ToS warning."
  fi
}

final_summary() {
  step "Done"
  cat <<EOF
  Install path: $(pwd -P)
  Checkout dependencies/configuration only; no runtime was provisioned or activated.
  Deploy the bot only inside its service account's private rootless container.
  Deployment contract and activation holds: phase-II_v2/DISCORD_ONLY_DEPLOYMENT.md
  Edit configuration later: $(pwd -P)/.env
  Re-run the wizard: ./install.sh --local --reconfigure
  Update later: ./install.sh --local, or git pull --ff-only && ./install.sh --local
EOF
}

main() {
  banner_and_confirm
  install_core_system_deps
  verify_python
  clone_or_update
  install_python_deps
  configure_env
  final_summary
}

main "$@"

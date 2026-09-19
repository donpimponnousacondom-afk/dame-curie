// PM2 process definitions for dame-curie.
//
// ENV IS LOADED BY PYTHON, NOT HERE. config.py and api/storage.py both call
// load_dotenv(override=True) on every process start, so the local .env file
// is the single source of truth — edit .env, `pm2 restart`, done. No env
// merging in this file (PM2 caches env from first start and --update-env
// does NOT re-read .env, which used to pin stale values like the old
// OPENAI_FALLBACK_MODEL forever).
//
// Only runtime flags that must exist before the interpreter boots live here:
// PYTHONUNBUFFERED (live logs). Everything else belongs in .env.

const fs = require("fs");
const os = require("os");
const path = require("path");

const appRoot = process.env.DAME_CURIE_APP_ROOT || __dirname;

// Ollama is only managed here when this machine actually has it. A fresh
// install that talks to a hosted endpoint would otherwise get a crash-looping
// `ollama serve` process it never asked for. Force either way with
// DAME_CURIE_PM2_OLLAMA=true|false.
function hasOllama() {
	const forced = (process.env.DAME_CURIE_PM2_OLLAMA || "").toLowerCase();
	if (forced === "true" || forced === "1") return true;
	if (forced === "false" || forced === "0") return false;
	return (process.env.PATH || "")
		.split(path.delimiter)
		.some((dir) => dir && fs.existsSync(path.join(dir, "ollama")));
}

// The checkout .venv is the only supported host interpreter; no global fallback.
const venvPython = path.join(appRoot, ".venv", "bin", "python");
const logsRoot = path.join(process.env.PM2_HOME || path.join(os.homedir(), ".pm2"), "logs");

const apps = [
	{
		name: "dame-curie-bot",
		script: "bot.py",
		interpreter: venvPython,
		cwd: appRoot,
		instances: 1,
		exec_mode: "fork",
		autorestart: true,
		watch: false,
		max_memory_restart: "1G",
		kill_timeout: 20000,
		kill_retry_time: 5000,
		kill_signal: "SIGTERM",
		stop_exit_codes: [2],
		exp_backoff_restart_delay: 3000,
		max_restarts: 15,
		min_uptime: 15000,
		restart_delay: 2000,
		listen_timeout: 10000,
		env: {
			PYTHONUNBUFFERED: "1",
			PYTHONDONTWRITEBYTECODE: "1",
		},
		log_date_format: "YYYY-MM-DD HH:mm:ss Z",
		merge_logs: true,
		error_file: path.join(logsRoot, "dame-curie-bot-error.log"),
		out_file: path.join(logsRoot, "dame-curie-bot-out.log"),
		log_type: "json",
	},
	{
		// Local Ollama serves only the RAG embedding model (qwen3-embedding).
		// Remote OpenAI-compatible inference is configured separately.
		// It runs here rather than under systemd because
		// the packaged unit runs as user `ollama` with HOME=/usr/share/ollama,
		// whose model store is empty — the 2.3G of pulled models live in
		// /root/.ollama and /root is 0700. pm2 runs as root, so it sees them.
		// The systemd unit is stopped and disabled; don't re-enable it
		// without moving the model store first.
		name: "ollama",
		script: "ollama",
		args: "serve",
		interpreter: "none",
		cwd: appRoot,
		instances: 1,
		autorestart: true,
		watch: false,
		kill_timeout: 10000,
		kill_signal: "SIGTERM",
		env: {
			// The model store lives under the invoking user's HOME.
			HOME: process.env.HOME || "/root",
			OLLAMA_ORIGINS: "*",
		},
		log_date_format: "YYYY-MM-DD HH:mm:ss Z",
		merge_logs: true,
	},
	{
		name: "dame-curie-api",
		script: "api/api_server.py",
		interpreter: venvPython,
		cwd: appRoot,
		instances: 1,
		exec_mode: "fork",
		autorestart: true,
		watch: false,
		max_memory_restart: "512M",
		kill_timeout: 10000,
		kill_retry_time: 3000,
		kill_signal: "SIGTERM",
		exp_backoff_restart_delay: 3000,
		max_restarts: 15,
		min_uptime: 10000,
		restart_delay: 1500,
		listen_timeout: 8000,
		env: {
			PYTHONUNBUFFERED: "1",
			PYTHONDONTWRITEBYTECODE: "1",
		},
		log_date_format: "YYYY-MM-DD HH:mm:ss Z",
		merge_logs: true,
		error_file: path.join(logsRoot, "dame-curie-api-error.log"),
		out_file: path.join(logsRoot, "dame-curie-api-out.log"),
		log_type: "json",
	},
];

module.exports = {
	apps: hasOllama() ? apps : apps.filter((app) => app.name !== "ollama"),
};

module.exports = {
  apps: [
    {
      name: 'dame-curie-bot',
      script: 'bot.py',
      interpreter: '.venv/bin/python',
      cwd: process.env.DAME_CURIE_APP_ROOT || __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: { NODE_ENV: 'production', PYTHONUNBUFFERED: '1' }
    },
    {
      name: 'dame-curie-api',
      script: 'api/api_server.py',
      interpreter: '.venv/bin/python',
      cwd: process.env.DAME_CURIE_APP_ROOT || __dirname,
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: { NODE_ENV: 'production', PYTHONUNBUFFERED: '1' }
    }
  ]
};

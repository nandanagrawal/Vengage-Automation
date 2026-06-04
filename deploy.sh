#!/bin/bash
set -e

REPO_DIR="/home/nandan.agrawal/Vengage-Automation"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
VENV_PIP="$BACKEND_DIR/venv/bin/pip"
VENV_UVICORN="$BACKEND_DIR/venv/bin/uvicorn"

echo "==> Pulling latest code..."
cd "$REPO_DIR"
git pull origin master

echo "==> Installing backend dependencies..."
cd "$BACKEND_DIR"
$VENV_PIP install -r requirements.txt --quiet

echo "==> Running database migrations..."
"$BACKEND_DIR/venv/bin/alembic" upgrade head

echo "==> Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --legacy-peer-deps

echo "==> Building frontend..."
npm run build

echo "==> Copying build to /var/www..."
sudo cp -rf "$FRONTEND_DIR/.next" /var/www/Vengage-Automation/frontend/

echo "==> Restarting services..."
# Always delete and recreate backend to ensure --cwd and interpreter are correct
pm2 delete backend 2>/dev/null || true
pm2 start "$VENV_UVICORN" \
  --name backend \
  --interpreter "$VENV_PYTHON" \
  --cwd "$BACKEND_DIR" \
  -- app.main:app --host 0.0.0.0 --port 8000

# Start frontend if not already registered, otherwise restart
if pm2 describe frontend > /dev/null 2>&1; then
  pm2 restart frontend --update-env
else
  cd "$FRONTEND_DIR"
  pm2 start "npm start" --name frontend
fi

pm2 save

echo ""
pm2 status
echo ""
echo "==> Deploy complete."

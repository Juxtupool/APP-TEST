#!/bin/bash
# ==============================================================================
# Overcontrol PocketBase 1-Click Automated Setup for GCP VM
# ==============================================================================
set -e

echo "=========================================="
echo " Starting PocketBase Full Setup on GCP... "
echo "=========================================="

# 1. Detect Architecture
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    PB_ARCH="linux_amd64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    PB_ARCH="linux_arm64"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

# 2. Install Dependencies
echo "[1/6] Installing unzip & curl..."
sudo apt-get update -y && sudo apt-get install -y unzip curl

# 3. Create Directories
echo "[2/6] Setting up /opt/pocketbase directory..."
sudo mkdir -p /opt/pocketbase/pb_migrations
sudo mkdir -p /opt/pocketbase/pb_data
sudo chown -R $USER:$USER /opt/pocketbase
cd /opt/pocketbase

# 4. Download PocketBase Binary
PB_VERSION="0.22.21"
echo "[3/6] Downloading PocketBase v${PB_VERSION} (${PB_ARCH})..."
wget -q https://github.com/pocketbase/pocketbase/releases/download/v${PB_VERSION}/pocketbase_${PB_VERSION}_${PB_ARCH}.zip -O pocketbase.zip
unzip -o pocketbase.zip
rm pocketbase.zip
chmod +x pocketbase

# 5. Create Migrations
echo "[4/6] Generating database schema migrations..."

cat << 'EOF' > /opt/pocketbase/pb_migrations/1784403473_created_macros.js
/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "52p56pklkn98iqu",
    "name": "macros",
    "type": "base",
    "system": false,
    "schema": [
      { "name": "name", "type": "text", "required": true },
      { "name": "author", "type": "text", "required": false },
      { "name": "description", "type": "text", "required": false },
      {
        "name": "category",
        "type": "select",
        "options": {
          "maxSelect": 1,
          "values": ["productivity", "creative", "gaming", "entertainment", "office", "other"]
        }
      },
      { "name": "tags", "type": "json" },
      {
        "name": "type",
        "type": "select",
        "options": { "maxSelect": 1, "values": ["macro", "profile"] }
      },
      { "name": "macro_data", "type": "json" },
      { "name": "profile_data", "type": "json" },
      { "name": "likes", "type": "number", "options": { "min": 0, "noDecimal": true } },
      { "name": "downloads", "type": "number", "options": { "min": 0, "noDecimal": true } },
      { "name": "approved", "type": "bool" }
    ],
    "listRule": "approved = true",
    "viewRule": "approved = true",
    "createRule": "",
    "updateRule": "@request.data.name:isset = false && @request.data.macro_data:isset = false && @request.data.profile_data:isset = false && @request.data.author:isset = false && @request.data.description:isset = false && @request.data.category:isset = false && @request.data.tags:isset = false && @request.data.approved:isset = false",
    "deleteRule": null
  });
  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("52p56pklkn98iqu");
  return dao.deleteCollection(collection);
});
EOF

cat << 'EOF' > /opt/pocketbase/pb_migrations/1784657000_created_crash_reports.js
/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "crash_reports_col",
    "name": "crash_reports",
    "type": "base",
    "system": false,
    "schema": [
      { "name": "app_version", "type": "text", "required": false },
      { "name": "os_info", "type": "text", "required": false },
      { "name": "error_type", "type": "text", "required": true, "presentable": true },
      { "name": "error_message", "type": "text", "required": false },
      { "name": "stack_trace", "type": "text", "required": false },
      { "name": "source", "type": "text", "required": false },
      { "name": "metadata", "type": "json", "required": false, "options": { "maxSize": 5242880 } }
    ],
    "listRule": null,
    "viewRule": null,
    "createRule": "",
    "updateRule": null,
    "deleteRule": null
  });
  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("crash_reports_col");
  return dao.deleteCollection(collection);
});
EOF

# Run migrations
./pocketbase migrate up

# 6. Configure Systemd Service
echo "[5/6] Creating & starting systemd service (pocketbase.service)..."
sudo bash -c 'cat <<EOF > /etc/systemd/system/pocketbase.service
[Unit]
Description=PocketBase Server for Overcontrol
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/pocketbase
ExecStart=/opt/pocketbase/pocketbase serve --http="0.0.0.0:8080"
Restart=always
RestartSec=5
StandardOutput=append:/var/log/pocketbase.log
StandardError=append:/var/log/pocketbase.error.log

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable pocketbase
sudo systemctl restart pocketbase

# 7. Configure Firewall
if command -v ufw > /dev/null; then
    sudo ufw allow 8080/tcp > /dev/null 2>&1 || true
fi

# 8. Health Verification
echo "[6/6] Verifying service health..."
sleep 2

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health || echo "failed")
PUBLIC_IP=$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")

echo ""
echo "=================================================================="
if [ "$HEALTH" = "200" ]; then
    echo " ✅ POCKETBASE IS FULLY INSTALLED AND RUNNING SUCCESSFULLY! "
else
    echo " ⚠️ Service started. Health check status: $HEALTH"
fi
echo "=================================================================="
echo " - Admin UI URL:      http://${PUBLIC_IP}:8080/_/"
echo " - Public API Base:   http://${PUBLIC_IP}:8080"
echo " - Collections Ready: 'macros' & 'crash_reports'"
echo " - Service Command:   sudo systemctl status pocketbase"
echo ""
echo "👉 Action for Overcontrol config.json:"
echo "   \"pocketbase\": { \"url\": \"http://${PUBLIC_IP}:8080\" }"
echo "=================================================================="

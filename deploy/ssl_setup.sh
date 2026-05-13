#!/usr/bin/env bash
# deploy/ssl_setup.sh
# ─────────────────────────────────────────────────────────────────────────────
# One-time SSL certificate setup for api.dialeasy.easyian.com
# Uses Certbot (Let's Encrypt) — free, auto-renewing, no wildcard needed.
#
# Run as root or with sudo on your production server.
# Prerequisites: Nginx installed, DNS A record for api.dialeasy.easyian.com
#                pointing to this server's IP.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DOMAIN="api.dialeasy.easyian.com"
EMAIL="admin@easyian.com"          # Change to your real email (for cert expiry alerts)

echo "============================================================"
echo "  DialEasy API — SSL Certificate Setup"
echo "  Domain : $DOMAIN"
echo "  Email  : $EMAIL"
echo "============================================================"

# ── 1. Install Certbot if not present ────────────────────────────────────────
if ! command -v certbot &>/dev/null; then
    echo "[1/4] Installing Certbot..."
    apt-get update -qq
    apt-get install -y certbot python3-certbot-nginx
else
    echo "[1/4] Certbot already installed ✓"
fi

# ── 2. Verify DNS resolves to this server ────────────────────────────────────
echo "[2/4] Checking DNS for $DOMAIN..."
RESOLVED_IP=$(dig +short "$DOMAIN" | tail -n1)
MY_IP=$(curl -s https://api.ipify.org)

if [ "$RESOLVED_IP" != "$MY_IP" ]; then
    echo ""
    echo "⚠️  WARNING: $DOMAIN resolves to $RESOLVED_IP"
    echo "   This server's public IP is $MY_IP"
    echo ""
    echo "   If DNS has not propagated yet, wait a few minutes and re-run."
    echo "   Proceeding anyway — Certbot will fail if DNS is wrong."
    echo ""
fi

# ── 3. Obtain certificate ─────────────────────────────────────────────────────
echo "[3/4] Requesting SSL certificate for $DOMAIN..."
certbot certonly \
    --nginx \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --redirect

echo "[3/4] Certificate issued ✓"
echo "      cert:    /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "      key:     /etc/letsencrypt/live/$DOMAIN/privkey.pem"

# ── 4. Enable Nginx site and reload ──────────────────────────────────────────
echo "[4/4] Enabling Nginx site and reloading..."
NGINX_CONF="/etc/nginx/sites-available/dialeasy_api"
NGINX_LINK="/etc/nginx/sites-enabled/dialeasy_api"

if [ ! -f "$NGINX_CONF" ]; then
    echo "⚠️  Nginx config not found at $NGINX_CONF"
    echo "   Copy deploy/nginx_central_api.conf to $NGINX_CONF first, then re-run."
    exit 1
fi

if [ ! -L "$NGINX_LINK" ]; then
    ln -s "$NGINX_CONF" "$NGINX_LINK"
    echo "   Symlink created: $NGINX_LINK"
fi

nginx -t && systemctl reload nginx
echo "[4/4] Nginx reloaded ✓"

# ── Auto-renewal check ────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  ✅ SSL setup complete!"
echo ""
echo "  Auto-renewal is handled by the Certbot systemd timer."
echo "  Verify with: systemctl status certbot.timer"
echo ""
echo "  Test your API:"
echo "    curl https://$DOMAIN/mobile/health/"
echo "============================================================"

#!/bin/bash
# Rotate the claude.ai session key stored in the Keychain.
# Run after logging out and back into claude.ai in the browser.

SERVICE="claude-usage"
ACCOUNT="session-key"
SWIFT=$(which swift)

echo "Current key fingerprint:"
OLD_HASH=$(security find-generic-password -s "$SERVICE" -a "$ACCOUNT" -w 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
if [ -z "$OLD_HASH" ]; then
    echo "  (none found)"
else
    echo "  $OLD_HASH"
fi

echo ""
echo "Paste the new sessionKey cookie value from DevTools, then press Enter:"
read -rs NEW_KEY
echo ""

if [ -z "$NEW_KEY" ]; then
    echo "No key entered. Aborting."
    exit 1
fi

NEW_HASH=$(echo -n "$NEW_KEY" | shasum -a 256 | cut -d' ' -f1)
if [ "$OLD_HASH" = "$NEW_HASH" ]; then
    echo "New key is identical to the old one. Did you log out first?"
    exit 1
fi

security delete-generic-password -s "$SERVICE" -a "$ACCOUNT" 2>/dev/null
security add-generic-password -s "$SERVICE" -a "$ACCOUNT" -w "$NEW_KEY" -T "$SWIFT" -T /usr/bin/security

echo "New key fingerprint:"
echo "  $NEW_HASH"
echo ""
echo "Done. Key rotated successfully."

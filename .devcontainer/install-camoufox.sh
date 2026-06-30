#!/bin/bash
set -e

for i in 1 2 3 4 5; do
    echo "Attempt $i/5: Installing Camoufox browser..."
    if python -c "from camoufox.pkgman import camoufox_path; camoufox_path()" 2>/dev/null; then
        echo "Camoufox installed successfully."
        exit 0
    fi
    echo "Rate limited. Waiting 30 seconds before retry..."
    sleep 30
done

echo "Error: Could not install Camoufox after 5 attempts."
echo "Set a GITHUB_TOKEN secret in your Codespace secrets for higher API limits."
exit 1

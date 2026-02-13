#!/usr/bin/env bash
# Download BGB XML from gesetze-im-internet.de
set -euo pipefail

DATA_DIR="$(cd "$(dirname "$0")/../data" && pwd)"
mkdir -p "$DATA_DIR"

URL="https://www.gesetze-im-internet.de/bgb/xml.zip"
ZIP_PATH="$DATA_DIR/bgb.zip"
XML_PATH="$DATA_DIR/bgb_mietrecht.xml"

echo "Downloading BGB XML from $URL..."
curl -L -o "$ZIP_PATH" "$URL"

echo "Extracting..."
cd "$DATA_DIR"
unzip -o "$ZIP_PATH" "*.xml" -d "$DATA_DIR"

# Rename the extracted XML file
XML_FILE=$(find "$DATA_DIR" -maxdepth 1 -name "*.xml" ! -name "bgb_mietrecht.xml" | head -1)
if [ -n "$XML_FILE" ]; then
    mv "$XML_FILE" "$XML_PATH"
fi

rm -f "$ZIP_PATH"
echo "Done: $XML_PATH"

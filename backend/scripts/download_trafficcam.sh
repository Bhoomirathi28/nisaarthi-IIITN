#!/usr/bin/env bash
# Downloads TrafficCAM (about 2,100 short clips from fixed traffic cameras in eight Indian cities)
# into backend/datasets/TrafficCAM. Source: https://math-ml-x.github.io/TrafficCAM/
# Please cite: Deng et al., "TrafficCAM: A Versatile Dataset for Traffic Flow Segmentation", IEEE T-ITS.
# The images are not committed to git (see .gitignore).
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q gdown
mkdir -p datasets/TrafficCAM/raw && cd datasets/TrafficCAM/raw

# Google Drive file IDs from the official download page
gdown 1h4oUqECDF05vSYMkYgz0aUc_RRzHlh3e -O Fully_annotate.zip
gdown 1lYz_aBX-4Ygj-tbUkHvsaPB3vxOIvGBA -O FirstFrame_annotate-1.zip
gdown 1TmN07tdC5NYpcIPI5tmhOrU1XfK7Yu6V -O FirstFrame_annotate-2.zip
gdown 1cKOpDQ-NvqTxIETXYcDOv_Ojc3UZm2Qq -O FirstFrame_annotate-3.zip

for z in *.zip; do unzip -q -o "$z"; done
mkdir -p FirstFrame_annotate
for part in FirstFrame_annotate-1 FirstFrame_annotate-2 FirstFrame_annotate-3; do
  if [ -d "$part" ]; then mv "$part"/* FirstFrame_annotate/ && rmdir "$part"; fi
done
rm -f *.zip && rm -rf __MACOSX
echo "Done. Clips: $(find . -mindepth 2 -maxdepth 2 -type d | wc -l)"
echo "Next: python scripts/build_street_index.py"

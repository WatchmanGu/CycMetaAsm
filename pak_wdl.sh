#!/bin/bash
set -euo pipefail
# This script is used to pack the WDL files into a single file that can be used by the CycloneFLow
docker save cycmetaasm:v1.1.0 | crabz -o ./wdl/combined_images.tar.gz -
cd wdl
zip -r task.zip task
cd ../
tar cfhv - wdl | crabz -o CycMetaAsm_V1.1.0.0.tar.gz -
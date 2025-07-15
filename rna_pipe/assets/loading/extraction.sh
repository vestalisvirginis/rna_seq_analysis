#!/bin/bash

# Create a raw files directory to untar files
mkdir -p  $RAW_DATA

# Ensure the directory was created successfully
if [ ! -d "$RAW_DATA" ]; then
    printf '%s\n' "Failed to create raw files directory."
    exit 1
fi
echo "Creating raw files directory:  $RAW_DATA"

# Extract all .tar files in the user_data directory
find  $INPUT_DATA  -name "*.tar" -type f -exec tar -xvf {} -C  $RAW_DATA \; 
echo "Extracted all .tar files to:  $RAW_DATA"
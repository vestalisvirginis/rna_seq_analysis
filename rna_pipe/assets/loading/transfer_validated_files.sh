#!/bin/bash

# Create destination directory for 
mkdir -p $FASTQ_DATA

# Extract .gz files and copy them
while IFS= read -r line; do
    if [[ $line == *.gz ]]; then
        # Create the destination directory structure
        #dir_name=$(dirname "temp/gz_files/${line#temp/raw_files/}")
       # mkdir -p "$dir_name"
        # Extract just the filename without path
        filename=$(basename "$line")
        # Copy the file, preserving directory structure
        cp "$line" "${FASTQ_DATA}/$filename"
    fi
done < ${RAW_DATA}/md5_validated_files.txt

# Verify the copy
echo "Copied files:"
find $FASTQ_DATA -name "*.gz" -type f
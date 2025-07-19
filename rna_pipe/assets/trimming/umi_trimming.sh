#!/bin/bash

# Create a fastqc output directory
mkdir -p  $UMI_TRIMMED_DATA

# Ensure the directory was created successfully
if [ ! -d "$UMI_TRIMMED_DATA" ]; then
    printf '%s\n' "Failed to create pre_fastqc_output directory."
    exit 1
fi
echo "Creating fastqc output directory:  $UMI_TRIMMED_DATA"

# Find and process each .gz file
find $FASTQ_DATA -name "*.gz" | while read -r fastq_file; do
    # Run UMI trimming on each file
    umi_tools extract --bc-pattern=NNNNCCCCNNN --log=${UMI_TRIMMED_DATA}/processed.log --stdin="$fastq_file" --stdout="$UMI_TRIMMED_DATA/$(basename "$fastq_file")"
done
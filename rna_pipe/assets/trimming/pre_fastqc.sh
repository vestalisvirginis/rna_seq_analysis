#!/bin/bash

# Create a fastqc output directory
mkdir -p  $PRE_FASTQC

# Ensure the directory was created successfully
if [ ! -d "$PRE_FASTQC" ]; then
    printf '%s\n' "Failed to create pre_fastqc_output directory."
    exit 1
fi
echo "Creating fastqc output directory:  $FASTQC_OUTPUT"

# Run FastQC on all .gz files in the specified directory
find ${PRE_FASTQC}/*.gz -exec fastqc -o ${FASTQC_OUTPUT} {} \;
#!/bin/bash

# Create a fastqc output directory
mkdir -p  $PRE_FASTQC

# Ensure the directory was created successfully
if [ ! -d "$PRE_FASTQC" ]; then
    printf '%s\n' "Failed to create pre_fastqc_output directory."
    exit 1
fi
echo "Creating fastqc output directory:  $PRE_FASTQC"

# Run FastQC on all .gz files in the specified directory
fastqc -V

find $FASTQ_DATA -name "*.gz" -exec fastqc -o ${PRE_FASTQC} {} \;
from dagster import asset, AssetExecutionContext, file_relative_path, PipesSubprocessClient, MaterializeResult, MetadataValue, open_pipes_session, PipesTempFileContextInjector, PipesTempFileMessageReader

import shutil
import subprocess
import os
from pathlib import Path


@asset(
    description="Convert SAM files to BAM format",
    deps=["mapping"],
    compute_kind="bash",
)
def convert_sam_to_bam(context: AssetExecutionContext):

    # Define paths
    MAPPING_DIR = "/data/mapping_output"
    QUANTIFICATION_DIR = "/data/quantification"

    # Create output directory
    Path(QUANTIFICATION_DIR).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(QUANTIFICATION_DIR):
        context.log.error(f"Failed to create directory: {QUANTIFICATION_DIR}")
        raise RuntimeError("Failed to create quantification directory")
    
    context.log.info(f"Creating quantification directory: {QUANTIFICATION_DIR}")

    # Check samtools version
    version_result = subprocess.run(
        ["samtools", "--version"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"Samtools version: {version_result.stdout}")

    # Conversion
    os.system(f"find {MAPPING_DIR} -name '*.sam' | while read -r sam_file; do samtools view -bS $sam_file > {QUANTIFICATION_DIR}/$(basename $sam_file .sam).bam; done")

    context.add_output_metadata(
            metadata={
                "version": MetadataValue.text(version_result.stdout),
            }
        )

    return QUANTIFICATION_DIR


@asset(
    description="Sorted BAM files",
    deps=["convert_sam_to_bam"],
    compute_kind="bash",
)
def sort_bam_files(context: AssetExecutionContext):

    # Define paths
    QUANTIFICATION_DIR = "/data/quantification"

    # Check samtools version
    version_result = subprocess.run(
        ["samtools", "--version"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"Samtools version: {version_result.stdout}")

    # Sorting BAM files
    os.system(f"find {QUANTIFICATION_DIR} -name '*.bam' | while read -r bam_file; do samtools sort $bam_file -o {QUANTIFICATION_DIR}/$(basename $bam_file .bam).sorted.bam; done")

    context.add_output_metadata(
            metadata={
                "version": MetadataValue.text(version_result.stdout),
            }
        )

    return QUANTIFICATION_DIR
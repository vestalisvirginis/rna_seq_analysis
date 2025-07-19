from dagster import asset, AssetExecutionContext, file_relative_path, PipesSubprocessClient, MaterializeResult, MetadataValue, open_pipes_session, PipesTempFileContextInjector, PipesTempFileMessageReader

import shutil
import subprocess
import os
from pathlib import Path


@asset(
    description="Indexing the reference genome",
    deps=["post_quality_check"],
    compute_kind="bash",
)
def indexing(context: AssetExecutionContext):

    # Define paths
    TRIMMED_DATA = "/data/trimmed_files"
    MAPPING_DIR = "/data/mapping_output"
    REFERENCE_DIR = "/input_data/references"

    # Define strain indexes
    strain_indexes = {
    "bacillus_subtilis_168": Path(REFERENCE_DIR, "168.fasta"),
    "bacillus_subtilis_mb8b7": Path(REFERENCE_DIR, "mb8b7.fasta"),
    "bacillus_subtilis_p9b1_lys_spbeta": Path(REFERENCE_DIR, "p9b1_lys_spbeta.fasta"),
   # "spbeta_168": Path(REFERENCE_DIR, "168.fasta"),
   # "spbeta_mb8b7": Path(REFERENCE_DIR, "mb8b7.fasta"),
}


    # Create output directory
    Path(MAPPING_DIR).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(MAPPING_DIR):
        context.log.error(f"Failed to create directory: {MAPPING_DIR}")
        raise RuntimeError("Failed to create mapping_output directory")
    
    context.log.info(f"Creating mapping output directory: {MAPPING_DIR}")

    # Check bowtie2 version
    version_result = subprocess.run(
        ["bowtie2", "--version"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"Bowtie2 version: {version_result.stdout}")

    # Get reference(s) for index
    count = 0
    for name, ref in strain_indexes.items():
        NAME = name
        REF = ref
        context.log.info(f"Indexing reference genome: {NAME} at {REF}")

        # Indexing the reference genome
        index_command = [
            "bowtie2-build", "-f", REF, f'{MAPPING_DIR}/{NAME}', "--threads", "6", ";"
        ]

        result = subprocess.run(index_command, capture_output=True, text=True)

        if result.returncode != 0:
            context.log.error(f"Indexing failed: {result.stderr}")
            raise RuntimeError(f"Indexing execution failed: {result.stderr}")
        
        context.log.info(f"Indexing completed successfully: {NAME}")
        count += 1

    context.add_output_metadata(
            metadata={
                "version": MetadataValue.text(version_result.stdout),
                "indexed_references": MetadataValue.text(", ".join(strain_indexes.keys())),
                "mapping_directory": MetadataValue.text(MAPPING_DIR),
                "count": MetadataValue.int(count),

            }
        )

    return MAPPING_DIR

@asset(
    description="Alignement of the reads against the reference genome",
    deps=["indexing"],
    compute_kind="bash",
)
def mapping(context: AssetExecutionContext):

    # Define paths
    TRIMMED_DATA = "/data/trimmed_files"
    MAPPING_DIR = "/data/mapping_output"

    # Check bowtie2 version
    version_result = subprocess.run(
        ["bowtie2", "--version"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"Bowtie2 version: {version_result.stdout}")
    
    # Map reads to the reference genome
    # mapping_command = [
    #     "bowtie2", "-x", f"{MAPPING_DIR}/bacillus_subtilis_p9b1_lys_spbeta", "-1", f"{TRIMMED_DATA}/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz", "-2", f"{TRIMMED_DATA}/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_2.fq.gz", "-S", f"{MAPPING_DIR}/aligned.sam", "-t", "--threads", "6", ";"
    # ]
    mapping_command = [
        "bowtie2",
        "-x", f"{MAPPING_DIR}/bacillus_subtilis_p9b1_lys_spbeta",
        "-1", f"{TRIMMED_DATA}/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz",
        "-2", f"{TRIMMED_DATA}/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_2.fq.gz",
        "-S", f"{MAPPING_DIR}/aligned.sam",
        "-t", 
        "--threads", "6"
    ]

    result = subprocess.run(mapping_command, capture_output=True, text=True)

    if result.returncode != 0:
        context.log.error(f"Bowtie2 failed: {result.stderr}")
        raise RuntimeError(f"Bowtie2 execution failed: {result.stderr}")
    
    context.log.info(f"Bowtie2 completed successfully: {result.stdout}")

    context.add_output_metadata(
            metadata={
                "command_stdout": MetadataValue.text(result.stdout),

            }
        )

    return MAPPING_DIR
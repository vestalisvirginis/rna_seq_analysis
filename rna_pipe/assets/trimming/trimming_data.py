from dagster import asset, AssetExecutionContext, file_relative_path, PipesSubprocessClient, MaterializeResult, MetadataValue, open_pipes_session, PipesTempFileContextInjector, PipesTempFileMessageReader

import shutil
import subprocess
import os
from pathlib import Path


@asset(
    description="Quality check before trimming",
    deps=["transfer_validated_files"],
    compute_kind="bash",
)
def pre_quality_check(context: AssetExecutionContext) -> str:
    """Run FastQC analysis on FASTQ files"""
    
    # Define paths
    FASTQ_DATA = "/data/fastq_files"
    PRE_FASTQC = "/data/pre_fastqc_output"
   
    
    # Create output directory
    Path(PRE_FASTQC).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(PRE_FASTQC):
        context.log.error(f"Failed to create directory: {PRE_FASTQC}")
        raise RuntimeError("Failed to create pre_fastqc_output directory")
    
    context.log.info(f"Creating fastqc output directory: {PRE_FASTQC}")
    
    # Check FastQC version
    version_result = subprocess.run(
        ["fastqc", "-V"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"FastQC version: {version_result.stdout}")
    
    # Run FastQC on all .gz files
    find_command = [
        "find", FASTQ_DATA, "-name", "*.gz", 
        "-exec", "fastqc", "-o", PRE_FASTQC, "{}", ";"
    ]
    
    result = subprocess.run(find_command, capture_output=True, text=True)
    
    if result.returncode != 0:
        context.log.error(f"FastQC failed: {result.stderr}")
        raise RuntimeError(f"FastQC execution failed: {result.stderr}")
    
    context.log.info(f"FastQC completed successfully: {result.stdout}")

    context.add_output_metadata(
            metadata={
                "command_stdout": MetadataValue.text(result.stdout),

            }
        )

    return PRE_FASTQC



@asset(
    description="Trim UMI adapters from sequence reads",
    deps=["pre_quality_check"],
    compute_kind="bash",
)
def umi_adapter_trimming(context: AssetExecutionContext) -> str:
    """Run UMI-Tools trimming on FASTQ files"""

    # Define paths
    FASTQ_DATA = "/data/fastq_files"
    UMI_TRIMMED_DATA = "/data/umi_trimmed_files"


    # Create output directory
    Path(UMI_TRIMMED_DATA).mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(UMI_TRIMMED_DATA):
        context.log.error(f"Failed to create directory: {UMI_TRIMMED_DATA}")
        raise RuntimeError("Failed to create umi_trim directory")
    
    context.log.info(f"Creating umi_trimmed directory: {UMI_TRIMMED_DATA}")
    
    # Check UMI-Tools version
    version_result = subprocess.run(
        ["umi_tools", "--version"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"UMI-Tools version: {version_result.stdout}")

    # Run UMI-Tools on all .gz files
    find_command = [
        "find", FASTQ_DATA, "-name", "*.gz",
    ]
    extract_command = [
        "while", "read", "-r", "fastq_file", ";", "do",
        "echo", "Processing file:", "$fastq_file",
        "done",
    ]

    # find_command = [
    #     "find", FASTQ_DATA, "-name", "*.gz", "|", "while", "read", "-r", "fastq_file", ";", "do",
    #     "echo", "Processing file:", "$fastq_file",
    #     "done",
    # ]
    # find_command = [
    #     "find", FASTQ_DATA, "-name", "*.gz", 
    #     "-exec", "umi_tools", "extract", "--bc-pattern", "NNNNCCCCNNN", "{}", ";" #"--log", log_path, "--stdin", "{}", "--stdout", f"{UMI_TRIMMED_DATA}/$(basename "{}")", ";"
    #    # "-exec", "fastqc", "-o", PRE_FASTQC, "{}", ";"
    # ]
    
    
    os.system(f"find {FASTQ_DATA} -name '*.gz' | while read -r fastq_file; do umi_tools extract --bc-pattern=NNNNCCCCNNN --stdin=\"$fastq_file\" --stdout=\"{UMI_TRIMMED_DATA}/$(basename \"$fastq_file\")\" --log=\"{UMI_TRIMMED_DATA}/processed.log\"; done")

    # if result.returncode != 0:
    #     context.log.error(f"UMI_trimmed failed: {result.stderr}")
    #     raise RuntimeError(f"UMI execution failed: {result.stderr}")
    
    # context.log.info(f"UMI_trim completed successfully: {result.stdout}")

    context.add_output_metadata(
            metadata={
                "file path": MetadataValue.text(UMI_TRIMMED_DATA),
                "UMI-Tools version": (version_result.stdout),
                #"Result": MetadataValue.text(result.stdout),
            }
        )

    return UMI_TRIMMED_DATA
    

@asset(
    description="Trim 3' nucleotides from sequence reads",
    deps=["umi_adapter_trimming"],
    compute_kind="bash",
)
def nucleotide_trimming(context: AssetExecutionContext):
    """Run Fastp trimming on FASTQ files"""

    # Define paths
    UMI_TRIMMED_DATA = "/data/umi_trimmed_files"
    TRIMMED_DATA = "/data/trimmed_files"
   
    
    # Create output directory
    Path(TRIMMED_DATA).mkdir(parents=True, exist_ok=True)

    if not os.path.exists(TRIMMED_DATA):
        context.log.error(f"Failed to create directory: {TRIMMED_DATA}")
        raise RuntimeError("Failed to create trimmed_files directory")

    context.log.info(f"Creating fastqc output directory: {TRIMMED_DATA}")
    
    # Check Cutadapt version
    version_result = subprocess.run(
        ["fastp", "-V"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"Fastp version: {version_result.stdout}")

    # Run Fastp on all .gz files
    os.system(f"find {UMI_TRIMMED_DATA} -name '*.gz' | while read -r fastq_file; do fastp --trim_front1 3 --length_required 20 -i \"$fastq_file\" -o \"{TRIMMED_DATA}/$(basename \"$fastq_file\")\" --html \"{TRIMMED_DATA}/report.html\" --json \"{TRIMMED_DATA}/report.json\" --thread 5 ; done")

    context.add_output_metadata(
            metadata={
                "Fastp version": MetadataValue.text(version_result.stdout),

            }
        )

    return TRIMMED_DATA

@asset(
    description="Post-quality check after trimming",
    deps=["nucleotide_trimming"],
    compute_kind="bash",
)
def post_quality_check(context: AssetExecutionContext):
    """Run FastQC analysis on FASTQ files"""
    
    # Define paths
    FASTQ_DATA = "/data/fastq_files"
    UMI_TRIMMED_DATA = "/data/umi_trimmed_files"
    TRIMMED_DATA = "/data/trimmed_files"
    POST_FASTQC = "/data/post_fastqc_output"
   
    
    # Create output directory
    Path(POST_FASTQC).mkdir(parents=True, exist_ok=True)

    if not os.path.exists(POST_FASTQC):
        context.log.error(f"Failed to create directory: {POST_FASTQC}")
        raise RuntimeError("Failed to create post_fastqc_output directory")

    context.log.info(f"Creating fastqc output directory: {POST_FASTQC}")
    
    # Check FastQC version
    version_result = subprocess.run(
        ["fastqc", "-V"], 
        capture_output=True, 
        text=True
    )
    context.log.info(f"FastQC version: {version_result.stdout}")
    
    # Run FastQC on all .gz files
    find_command = [
        "find", TRIMMED_DATA, "-name", "*.gz", 
        "-exec", "fastqc", "-o", POST_FASTQC, "{}", ";"
    ]
    
    result = subprocess.run(find_command, capture_output=True, text=True)
    
    if result.returncode != 0:
        context.log.error(f"FastQC failed: {result.stderr}")
        raise RuntimeError(f"FastQC execution failed: {result.stderr}")
    
    context.log.info(f"FastQC completed successfully: {result.stdout}")

    context.add_output_metadata(
            metadata={
                "command_stdout": MetadataValue.text(result.stdout),

            }
        )

    return POST_FASTQC




# @asset
# def fastqc_analysis(context: AssetExecutionContext) -> None:
#     """Run FastQC analysis using Dagster Pipes"""
    
#     # Set environment variables that your script expects
#     env_vars = {
#         "PRE_FASTQC": "/data/pre_fastqc_output",
#         "FASTQ_DATA": "/data/fastq_files"
#     }
    
#     # Use PipesSubprocessClient to run your bash script
#     pipes_subprocess_client = PipesSubprocessClient()
    
#     result = pipes_subprocess_client.run(
#         command=["bash", "/usr/src/rna_pipe/assets/trimming/pre_fastqc.sh"],
#         context=context,
#         env=env_vars
#     ).get_materialize_result()
    
#     return "ok"
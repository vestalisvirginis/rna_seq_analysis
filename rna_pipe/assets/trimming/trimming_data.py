from dagster import asset, AssetExecutionContext, file_relative_path, PipesSubprocessClient, MaterializeResult, MetadataValue, open_pipes_session, PipesTempFileContextInjector, PipesTempFileMessageReader

import shutil
import subprocess


@asset(
    description="Quality check before trimming",
    deps=[transfer_validated_files],
    compute_kind="bash",
)
def pre_quality_check(context: AssetExecutionContext):
    bash_path = shutil.which("bash")
    cmd = [bash_path, "/usr/src/rna_pipe/assets/loading/pre_fastqc.sh"]
    with open_pipes_session(
        context=context,
        context_injector=PipesTempFileContextInjector(),
        message_reader=PipesTempFileMessageReader(),
    ) as pipes_session:
        process = subprocess.Popen(
            cmd,
            env={
            "FASTQ_DATA": "/data/fastq_files",
            "PRE_FASTQC": "/data/pre_fastqc_output",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
        )
        
        stdout, stderr = process.communicate()

        context.add_output_metadata(
            metadata={
                "command_stdout": MetadataValue.text(stdout),

            }
        )
        
        while process.poll() is None:
            yield from pipes_session.get_results()
        
        yield from pipes_session.get_results()

@asset()
def umi_adapter_trimming(pre_qualitity_check):
    return "This is a UMI adapter trimming asset."

@asset()
def nucleotide_trimming(umi_adapter_trimming):
    return "This is a nucleotide trimming asset."

@asset()
def post_quality_check(nucleotide_trimming):
    return "This is a post-quality check asset."
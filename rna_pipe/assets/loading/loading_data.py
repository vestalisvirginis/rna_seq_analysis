from dagster import asset, AssetExecutionContext, file_relative_path, PipesSubprocessClient, MaterializeResult, MetadataValue, open_pipes_session, PipesTempFileContextInjector, PipesTempFileMessageReader

import shutil
import subprocess


INPUT_FILE_DIR = '/input_data'


@asset(
    #required_resource_keys={"pipes_subprocess_client"},
    description="Extracts raw data from tar files",
    compute_kind="bash",
    #io_manager_key="io_manager",
    #metadata={"owner": OWNER},
)
def extraction(context: AssetExecutionContext):
    #cmd = [shutil.which("bash"),  file_relative_path(__file__, "loading/shell_test.sh")]
    bash_path = shutil.which("bash")
    cmd = [bash_path, "/usr/src/rna_pipe/assets/loading/extraction.sh"]
    with open_pipes_session(
        context=context,
        context_injector=PipesTempFileContextInjector(),
        message_reader=PipesTempFileMessageReader(),
    ) as pipes_session:
        process = subprocess.Popen(
            cmd,
            env={
            "INPUT_DATA": INPUT_FILE_DIR,
            "RAW_DATA": "/data/raw_data",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
        )
        
        stdout, stderr = process.communicate()

        context.add_output_metadata(
            metadata={"command_stdout": MetadataValue.text(stdout)}
        )
        
        while process.poll() is None:
            yield from pipes_session.get_results()
        
        yield from pipes_session.get_results()

@asset(
    description="Validates the integrity of extracted data",
    deps=[extraction],
    compute_kind="bash",
)
def validation(context: AssetExecutionContext):
    bash_path = shutil.which("bash")
    cmd = [bash_path, "/usr/src/rna_pipe/assets/loading/md5_validation.sh"]
    with open_pipes_session(
        context=context,
        context_injector=PipesTempFileContextInjector(),
        message_reader=PipesTempFileMessageReader(),
    ) as pipes_session:
        process = subprocess.Popen(
            cmd,
            env={
            "RAW_DATA": "/data/raw_data",
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



@asset(
    description="Transfers validated files to fastq directory",
    deps=[validation],
    compute_kind="bash",
)
def transfer_validated_files(context: AssetExecutionContext):
    bash_path = shutil.which("bash")
    cmd = [bash_path, "/usr/src/rna_pipe/assets/loading/transfer_validated_files.sh"]
    with open_pipes_session(
        context=context,
        context_injector=PipesTempFileContextInjector(),
        message_reader=PipesTempFileMessageReader(),
    ) as pipes_session:
        process = subprocess.Popen(
            cmd,
            env={
            "RAW_DATA": "/data/raw_data",
            "FASTQ_DATA": "/data/fastq_files",
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
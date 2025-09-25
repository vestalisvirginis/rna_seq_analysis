import subprocess
from glob import glob
from pathlib import Path

from dagster_pipes import open_dagster_pipes

with open_dagster_pipes() as context:
    result = subprocess.run(["samtools", "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    context.log.info(str(version))
    # context.report_asset_materialization(metadata={"bowtie2_tools_version": version})

    extras = context.extras
    context.log.info(str(extras))
    # bc_pattern = context.get_extra("bc_pattern")
    parallel_threads = context.get_extra("parallel_threads")

    inputs = Path("/inputs")
    Path("/outputs/bam_files").mkdir(parents=True, exist_ok=True)
    Path("/outputs/sorted_bam").mkdir(parents=True, exist_ok=True)

    context.log.info("SamTools: Started")

    find_proc = subprocess.Popen(
        ["find", "/inputs", "-name", "*.sam"], stdout=subprocess.PIPE
    )
    find = find_proc.stdout
    context.log.info(str(find))

    parallel_cmd = [
        "parallel",
        "-j",
        str(parallel_threads),
        "f={}; "
        'basename=$(basename "$f" .sam); '
        'samtools view -bS "$f" > "/outputs/bam_files/${basename}.bam" && '
        'samtools sort "/outputs/bam_files/${basename}.bam" -o "/outputs/sorted_bam/${basename}.sorted.bam"',
    ]
    context.log.info(
        parallel_cmd
    )  # no multi threading --> only use one thread per file --> code do not work

    output = subprocess.run(
        parallel_cmd, stdin=find_proc.stdout, capture_output=True, text=True
    )
    find_proc.stdout.close()

    context.log.info("SamTools: Completed")

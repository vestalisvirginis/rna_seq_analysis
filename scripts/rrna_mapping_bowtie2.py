import re
import subprocess
from pathlib import Path

from dagster_pipes import open_dagster_pipes
from toolz import compose, juxt, pluck
from toolz.curried import map as cmap

with open_dagster_pipes() as context:
    result = subprocess.run(["bowtie2", "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    context.log.info(str(version))
    #context.report_asset_materialization(metadata={"bowtie2_tools_version": version})


    parallel_threads = context.get_extra("parallel_threads")

    #######
    inputs = Path("/inputs")
    output_folder = Path("/outputs")
    result_path = output_folder / "bowtie2"
    result_path.mkdir(parents=True, exist_ok=True)
    index_folder = Path('/index') / "ribo"

    

    _get_gz_files = lambda x: x.glob("*.gz")
    _get_prefix = lambda x: re.split(r"_\d\.", x.name)[0]

    files = compose(set, cmap(_get_prefix))(list(_get_gz_files(inputs)))

    # get parameters for bowtie2
    _1 = lambda x: f"{inputs}/{x}_1.fq.gz"
    _2 = lambda x: f"{inputs}/{x}_2.fq.gz"
    _sam = lambda x: f"{result_path}/{x}.sam"


    def get_param(files: list) -> tuple:
        return juxt(compose(list, cmap(_1)), compose(list, cmap(_2)), compose(list, cmap(_sam)))(files)


    context.log.info("BowTie2: Started")

    context.log.info(f"Processing files: {len(files)} files")

    for i in range(len(files)):
        
        r1_fastq, r2_fastq, output_sam = pluck(i, get_param(files))

        context.log.info(f"Aligning {r1_fastq} and {r2_fastq} to rRNA index...")

        cmd = [
            "bowtie2",
            "-x",
            str(index_folder),
            "-1", 
            r1_fastq,
            "-2", 
            r2_fastq,
            "-S",
            output_sam,
            "--threads", 
            str(parallel_threads),
            "--no-unal"  # Only output aligned reads
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        context.log.info(result.stderr)  # Bowtie2 reports stats to stderr
        context.log.info(f"Done. Output SAM: {output_sam}")


    context.log.info("BowTie2: Completed")

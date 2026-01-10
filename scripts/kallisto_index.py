import re
import subprocess
from pathlib import Path
from glob import glob

from dagster_pipes import open_dagster_pipes
from toolz import compose, juxt
from toolz.curried import filter as cfilter
from toolz.curried import map as cmap

with open_dagster_pipes() as context:
    result = subprocess.run(["kallisto", "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    context.log.info(str(version))

    parallel_threads = context.get_extra("parallel_threads")

    inputs = Path("/inputs")
    output_folder = Path("/outputs")
    result_path = output_folder / "kallisto_indexes"
    result_path.mkdir(parents=True, exist_ok=True)

    context.log.info("Prepare kallisto indexes")

    for file in glob(str(inputs / '*' / "*.ffn")):
        context.log.info(file)
        file_name = Path(file).stem
        context.log.info(f"{file_name} index in preparation...")
        cmd = [
                "kallisto",
                "index",
                "-i",
                f"{result_path}/{file_name}.index",
                #"--aa",
                "-t",
                str(parallel_threads),
                file,
            ]
        index = subprocess.run(cmd, capture_output=True, text=True)
        context.log.info(f"{file_name} index completed")

    context.log.info("Indexes done")
import csv
import subprocess
from collections import namedtuple
from pathlib import Path, PosixPath

from dagster_pipes import open_dagster_pipes
from toolz.curried import map as cmap

with open_dagster_pipes() as context:
    result = subprocess.run(["prokka", "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    context.report_asset_materialization(metadata={"prokka_version": version})

    extras = context.extras
    context.log.info(str(extras))
    parallel_threads = context.get_extra("parallel_threads")
    reference_genomes = context.get_extra("reference_genomes")

    Genome = namedtuple("Genome", "name, locustag, genus, species, strain, kingdom")

    input_folder = Path("/inputs")
    output_folder = Path("/outputs")
    fasta_files = input_folder / "fasta"

    map(Genome._make, csv.reader(open(input_folder / reference_genomes)))

    def get_cmd(
        reference: namedtuple,
        cpus: int = parallel_threads,
        input_dir: PosixPath = fasta_files,
        output_dir: PosixPath = output_folder,
    ) -> list:
        return [
            "prokka",
            "--outdir",
            f"{output_dir} / {reference.name}",
            "--force",
            "--prefix",
            reference.name,
            "--addgenes",
            "--locustag",
            reference.locustag,
            "--increment",
            "10",
            "--genus",
            reference.genus,
            "--species",
            reference.species,
            "--strain",
            reference.strain,
            "--kingdom",
            reference.kingdom,
            "--cpus",
            str(cpus),
            f"{input_dir} / {reference.name}.fasta",
        ]

    def run_cmd(command: list):
        return subprocess.run(command, capture_output=True, text=True)

    context.log.info("Prokka: Started")
    list(
        cmap(
            run_cmd,
            cmap(
                get_cmd,
                cmap(Genome._make, csv.reader(open(input_folder / reference_genomes))),
            ),
        )
    )
    # output = subprocess.run(pre_command + files, capture_output=True, text=True)
    context.log.info("Prokka: Completed")

    # prokka --outdir /outputs/168 --force --prefix 168 --addgenes --locustag PA168 --increment 10 --genus Bacillus --species subtilis --strain 168 --kingdom Bacteria --cpus 6 /inputs/fasta/168.fasta

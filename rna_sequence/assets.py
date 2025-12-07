import hashlib
import os
from functools import partial
from glob import glob
from itertools import chain
from operator import attrgetter as at
from operator import methodcaller as mc
from pathlib import Path
from typing import Iterator, List, Tuple

from dagster_docker import PipesDockerClient
from toolz import compose, curry, first, last, pipe
from toolz.curried import filter as cfilter

import dagster as dg
import shutil

class RnaSequenceConfig(dg.Config):
    input_pattern: str = "MD5.txt"
    input_folder: str = "data"

    fastq_pattern: str = "*.gz"
    output_folder: str = "/outputs"

    umi_bc_pattern: str = "NNNNCCCCNNN"
    umi_parallel: int = 40

    fastp_parallel: int = 40

    bowtie_parallel: int = 40

    samtools_parallel: int = 40

    prokka_parallel: int = 6
    genomes: str = "references.csv"


@dg.asset(
    check_specs=[
        dg.AssetCheckSpec(
            name="files_found",
            description="Validates existance of md5 files",
            asset="fasta_md5",
            blocking=False,
        )
    ],
    kinds={"python"},
)
def fasta_md5(
    context: dg.AssetExecutionContext, config: RnaSequenceConfig
) -> Iterator[dg.Output[List[Tuple[str, str]]]]:
    """Retrive MD5 files"""
    files: List[str] = glob(
        str(Path(config.input_folder) / "**" / config.input_pattern)
    )
    pairs = []
    for file in files:
        with open(file, "r") as fd:
            for line in fd.readlines():
                pair = tuple(line.strip().split())
                context.log.info(pair)
                pairs.append(pair)

    yield dg.AssetCheckResult(passed=len(pairs) > 0, check_name="files_found")

    yield dg.Output(value=pairs, metadata={"dagster/num_rows": len(pairs)})


@dg.asset(
    check_specs=[
        dg.AssetCheckSpec(
            name="files_found",
            description="Validates existance of gz files",
            asset="fasta_gz",
            blocking=False,
        )
    ],
    kinds={"python"},
)
def fasta_gz(
    context: dg.AssetExecutionContext, config: RnaSequenceConfig
) -> Iterator[dg.Output[List[Tuple[str, str]]]]:
    """Retrieve GZ files"""

    def md5_file(filepath):
        """Compute MD5 hash of a file in chunks."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    files = glob(str(Path(config.input_folder) / "**" / config.fastq_pattern))
    context.log.info(str(files))
    hashes = []
    for file in files:
        md5_string = md5_file(file)
        pair = tuple([md5_string, Path(file).name])
        context.log.info(pair)
        hashes.append(pair)

    yield dg.AssetCheckResult(passed=len(hashes) > 0, check_name="files_found")

    yield dg.Output(value=hashes, metadata={"dagster/num_rows": len(hashes)})


@dg.asset(
    ins={
        "fasta_gz": dg.AssetIn(key="fasta_gz"),
        "fasta_md5": dg.AssetIn(key="fasta_md5"),
    },
    check_specs=[
        dg.AssetCheckSpec(
            name="valid_md5",
            description="Validates that md5 strings match the file content",
            asset="md5_validate",
            blocking=False,  
        )
    ],
    kinds={"python"},
)
def md5_validate(
    context: dg.AssetExecutionContext,
    fasta_gz: List[Tuple[str, str]],
    fasta_md5: List[Tuple[str, str]],
) -> Iterator[dg.Output[Tuple[bool, List[str]]]]:
    """Confirm all valid"""
    inventory = set(fasta_gz)
    result = inventory == set(fasta_md5)
    yield dg.AssetCheckResult(passed=result, check_name="valid_md5")

    _names = list(map(last, inventory))
    yield dg.Output(value=tuple([result, _names]))


@dg.asset(
    deps=[md5_validate],
    check_specs=[
        dg.AssetCheckSpec(
            name="concat_fastq",
            description="Concat re-sequenced fastq files",
            asset="fastq_concat",
            blocking=False,
        )
    ],
    kinds={"python"},
)
def fastq_concat(
    context: dg.AssetExecutionContext, config: RnaSequenceConfig
) -> Iterator[dg.Output[Tuple[bool, List[str]]]]:
    """Concat fastq files"""

    # Define paths

    input_folder = Path(config.input_folder)
    output_folder = Path(config.output_folder)
    context.log.info(str(input_folder))
    context.log.info(str(output_folder))

    # Create output directory if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)    
    
    matches = glob("**/*.gz")
    _has_1 = lambda x: "_1." in x.name    
    _has_2 = lambda x: "_2." in x.name

    # Transformations
    @curry
    def copy_file(dest_folder: Path, src_file: Path) -> str:
        """Copy file to destination and return destination filename"""
        dest = dest_folder / src_file.name
        shutil.copy2(src_file, dest)
        return dest.name

    @curry
    def cat_file(reads: int, dest_folder: Path, src_file: List[Path]) -> str:
        """Concatenate file to destination and return destination filename"""
        prefix = Path(os.path.commonprefix(src_file)).name
        input_str = " ".join(str(f) for f in src_file)
        output_file = dest_folder / f"{prefix}_merged_{reads}.fq.gz"
        os.system(f"cat {input_str} > {output_file}")
        return output_file.name

    # Get all subfolders in input folder
    subfolders = compose(list, chain.from_iterable, _getsubsubdirs, _get_subdirs)(
        input_folder
    )

    merged_files = []
    copied_files = []
    for subfolder in subfolders:
        # Get gz files in subfolder
        gz_files = list(_get_gz_files(subfolder))
        context.log.info(f"Found {len(gz_files)} files in {subfolder}")

        if len(gz_files) < 2:
            context.log.warning(f"Skipping {subfolder} - fewer than 2 files")
            continue

        # Copy files that don't need merging
        if len(gz_files) == 2:
            files = list(pipe(gz_files, partial(map, copy_file(output_folder))))
            context.log.info(f"Copied files: {files}")
            copied_files.append(files)
        else:
            files_1 = list(cfilter(_has_1, gz_files))
            files_2 = list(cfilter(_has_2, gz_files))

            context.log.info(f"Output folder: {output_folder}")
            cat_1 = cat_file(1, output_folder, files_1)
            cat_2 = cat_file(2, output_folder, files_2)
            merged_files.append(cat_1 + cat_2)

    processed_files = copied_files + merged_files
    success = len(processed_files) >= 2
    yield dg.AssetCheckResult(passed=success, check_name="concat_fastq")
    yield dg.Output(value=processed_files)


@dg.asset(
    deps=[fastq_concat],
    check_specs=[
        dg.AssetCheckSpec(
            name="full_sequence",
            description="Reports created for all sequences",
            asset="fastqc_runner",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def fastqc_runner(
    context: dg.AssetExecutionContext,
    docker_client: PipesDockerClient,
    md5_validate: Tuple[bool, List[str]],
) -> Iterator[dg.Output[str]]:
    """Docker execution of fastqc tool"""
    result = docker_client.run(
        image="fastqc",
        command=["python", "/scripts/fastqc.py"],
        context=context,
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "merged_fastq"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "pre_fastqc"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    files_io = os.listdir(
        str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outputs" / "pre_fastqc")
    )
    _, files_spec = md5_validate

    _stems = compose(first, mc("split", "-"), at("stem"), Path)
    _f_stems = list(map(_stems, files_spec))
    _f_outs = list(map(_stems, files_io))
    complete = set(_f_stems).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=complete, check_name="full_sequence")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[fastqc_runner],
    check_specs=[
        dg.AssetCheckSpec(
            name="adapter_trim",
            description="Trimming all sequences",
            asset="umitools_runner",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def umitools_runner(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of umi_tool tool"""
    result = docker_client.run(
        image="umitools",
        command=["python", "/scripts/umitools.py"],
        context=context,
        extras={
            "bc_pattern": config.umi_bc_pattern,
            "parallel_threads": config.umi_parallel,
        },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "merged_fastq"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "umi_trimmed"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="adapter_trim")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[umitools_runner],
    check_specs=[
        dg.AssetCheckSpec(
            name="nucleotide_trim",
            description="Trimming fastp nucleaotide check",
            asset="fastp_runner",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def fastp_runner(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of fastp tool"""
    result = docker_client.run(
        image="fastp",
        command=["python", "/scripts/fastp.py"],
        context=context,
        extras={"parallel_threads": config.fastp_parallel},
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "umi_trimmed"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "processed_fastq"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # TODO: add fastp_runner validation
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="nucleotide_trim")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[fastp_runner],
    check_specs=[
        dg.AssetCheckSpec(
            name="full_sequence",
            description="Reports created for all sequences",
            asset="fastqc_post",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def fastqc_post(
    context: dg.AssetExecutionContext,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of fastqc tool"""
    result = docker_client.run(
        image="fastqc",
        command=["python", "/scripts/fastqc.py"],
        context=context,
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "processed_fastq"
                    / "gz"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "post_fastqc"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # TODO: add validation fastqc_post
    # files_io = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs"))
    # _, files_spec = md5_validate

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_stems = list(map(_stems, files_spec))
    # _f_outs = list(map(_stems, files_io))
    # complete = set(_f_stems).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="full_sequence")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[fastqc_post],
    check_specs=[
        dg.AssetCheckSpec(
            name="annotation",
            description="Genome re-annotation",
            asset="prokka",
            blocking=True,
        )
    ],
    kinds={"docker"},
)
def prokka(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of prokka tool"""
    result = docker_client.run(
        image="prokka",
        command=["python", "/scripts/prokka.py"],
        context=context,
        extras={
            "parallel_threads": config.prokka_parallel,
            "reference_genomes": config.genomes,
        },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "references"): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "prokka_outputs"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[fastqc_post, prokka],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Indexing complet",
            asset="bowtie_index",
            blocking=True,
        )
    ],
    kinds={"docker"},
)
def bowtie_index(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of bowtie2-build tool"""
    result = docker_client.run(
        image="bowtie2",
        command=["python", "/scripts/bowtie2.py"],
        context=context,
        extras={
            "parallel_threads": config.bowtie_parallel,
        },
        container_kwargs={
            "auto_remove": False,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "references"): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "indexes"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[bowtie_index, fastp_runner],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Mapping complet",
            asset="bowtie_mapping",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def bowtie_mapping(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of bowtie2 tool"""
    result = docker_client.run(
        image="bowtie2",
        command=["python", "/scripts/bowtie2_mapping.py"],
        context=context,
        extras={
            "parallel_threads": config.bowtie_parallel,
        },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "processed_fastq"
                    / "gz"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "indexes"
                ): {
                    "bind": "/indexes",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outputs"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[fastp_runner],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Mapping complet",
            asset="kallisto_pseudo_mapping",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def kallisto_pseudo_mapping(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of bowtie2 tool"""
    result = docker_client.run(
        image="kallisto",
        command=["python", "/scripts/kallisto.py"],
        context=context,
        # extras={
        #    "parallel_threads": config.bowtie_parallel,
        # },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "processed_fastq"
                    / "gz"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "kallisto_indexes"
                ): {
                    "bind": "/indexes",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outputs"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[bowtie_mapping],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Samtools check placeholder",
            asset="samtools",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def samtools(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of samtools tool"""
    result = docker_client.run(
        image="samtools",
        command=["python", "/scripts/samtools.py"],
        context=context,
        extras={
            "parallel_threads": config.samtools_parallel,
        },
        container_kwargs={
            "auto_remove": False,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "bowtie2"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outputs"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[samtools],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Fadu check placeholder",
            asset="fadu_quantification",
            blocking=True,
        )
    ],
    kinds={"docker"},
)
def fadu_quantification(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of fadu tool"""
    result = docker_client.run(
        image="fadu",
        command=["python", "/scripts/fadu.py"],
        context=context,
        # extras={
        #     "parallel_threads": config.bowtie_parallel,
        # },
        container_kwargs={
            "auto_remove": False,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "bowtie2" / "inputs"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs5"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[samtools],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="Feature count check placeholder",
            asset="feature_counts",
            blocking=True,
        )
    ],
    kinds={"docker"},
)
def feature_counts(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of subread tool"""
    result = docker_client.run(
        image="subread",
        command=["python", "/scripts/subread.py"],
        context=context,
        # extras={
        #     "parallel_threads": config.bowtie_parallel,
        # },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "sorted_bam"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "outputs"
                    / "gtf_files"
                ): {
                    "bind": "/references",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outputs"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[feature_counts],
    check_specs=[
        dg.AssetCheckSpec(
            name="file_count",
            description="PyDeseq check placeholder",
            asset="differential_expression",
            blocking=True,
        )
    ],
    kinds={"docker"},
)
def differential_expression(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of subread tool"""
    result = docker_client.run(
        image="pydeseq2",
        command=["python", "/scripts/pydeseq2.py"],
        context=context,
        # extras={
        #     "parallel_threads": config.bowtie_parallel,
        # },
        container_kwargs={
            "auto_remove": False,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "bowtie2" / "inputs"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs5"): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outputs2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))

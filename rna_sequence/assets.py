import hashlib
import os
import duckdb
import subprocess
from lxml import html
from functools import partial
from glob import glob
from itertools import chain
from operator import attrgetter as at
from operator import methodcaller as mc
from pathlib import Path
from typing import Iterator, List, Tuple

from dagster_docker import PipesDockerClient
from toolz import compose, curry, first, last, pipe, groupby
from toolz.curried import filter as cfilter
from toolz.curried import valfilter as valfc

import dagster as dg


class RnaSequenceConfig(dg.Config):
    input_pattern: str = "MD5.txt"
    input_folder: str = "data/input/sequencing_data"

    fastq_pattern: str = "*.gz"
    output_folder: str = "data/output/pre_processing"

    umi_bc_pattern: str = "NNNNCCCCNNN"
    umi_parallel: int = 40

    fastp_parallel: int = 40

    bowtie_parallel: int = 40

    samtools_parallel: int = 40

    ribo_id_sam: str = "data/output/ribo_analysis/bowtie2"
    ribo_id_fastq: str = "data/output/pre_processing/umi_trimmed"
    ribo_id_clean: str = "data/output/ribo_analysis/clean_reads"
    ribo_id_rrna: str = "data/output/ribo_analysis/rrna_reads"

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
        str(Path(config.input_folder) / "**" / "**" / config.input_pattern)
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

    files = glob(str(Path(config.input_folder) / "**" / "**" / config.fastq_pattern))
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
            blocking=False,  # TODO implement a way to continue with files that pass the check and only block file/group of files that fail the check
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
            blocking=False,  # TODO implement a way to continue with files that pass the check and only block file/group of files that fail the check
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
    output_folder = Path(config.output_folder) / "preprocessed_fastq"
    context.log.info(str(input_folder))
    context.log.info(str(output_folder))

    # Create output directory if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)

    # Filters
    def _is_dir(x):
        return x.is_dir()

    # _is_dir = lambda x: x.is_dir()
    def _get_subdirs(x):
        return x.iterdir()

    # _get_subdirs = lambda x: x.iterdir()
    def _getsubsubdirs(dirs):
        return map(_get_subdirs, filter(_is_dir, dirs))

    # _getsubsubdirs = lambda dirs: map(_get_subdirs, filter(_is_dir, dirs))
    def _get_gz_files(x):
        return x.glob("*.gz")

    # _get_gz_files = lambda x: x.glob("*.gz")
    def _has_1(x):
        return "_1." in x.name

    # _has_1 = lambda x: "_1." in x.name
    def _has_2(x):
        return "_2." in x.name  # .name

    # _has_2 = lambda x: "_2." in x  # .name

    # Transformations
    @curry
    def copy_file(dest_folder: Path, src_file: Path) -> str:
        """Copy file to destination and return destination filename"""
        dest = dest_folder / src_file.name
        os.system(f"cp {src_file} {dest}")
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
                    / "output"
                    / "pre_processing"
                    / "preprocessed_fastq"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "pre_processing"
                    / "pre_fastqc"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    files_io = os.listdir(
        str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "output" / "pre_processing"/ "pre_fastqc")
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
                    / "output"
                    / "pre_processing"
                    / "preprocessed_fastq"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "pre_processing"
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
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                    / "output"
                    / "pre_processing"
                    / "umi_trimmed"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "pre_processing"
                    / "trim_fastq_2"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # TODO: add fastp_runner validation
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                    / "output"
                    / "pre_processing"
                    / "umi_trimmed"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "pre_processing"
                    / "post_fastqc_3"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # TODO: add validation fastqc_post
    # files_io = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp"))
    # _, files_spec = md5_validate

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_stems = list(map(_stems, files_spec))
    # _f_outs = list(map(_stems, files_io))
    # complete = set(_f_stems).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="full_sequence")

    yield dg.Output(value=str(result.get_results()))


def read_content(html_content: str) -> dict:
    tree = html.fromstring(html_content)
    header = ("file_name", "file_type", "encoding", "total_sequences", "total_bases", "poor_quality", "sequence_length", "pct_gc")
    values = tree.xpath("//h2[@id='M0']/following-sibling::table/tbody/tr/td[2]/text()")
    return dict(zip(header,values))

# @dg.asset_check(asset=fastqc_post)
# def content_check():
#     path = str(
#                     Path(os.getenv("RNA_SEQUENCE_HOME"))
#                     / "data"
#                     / "output"
#                     / "pre_processing"
#                     / "post_fastqc_3"
#                     / "*.html"
#                 )
#     files = glob(path)
#     _key = compose(first, mc("split", "_"), at("name"), Path)
#     pairs = {}
#     i = 0
#     for k,v in groupby(_key, files).items():
#         a,b = first(v), last(v)
#         with open(a, "r") as read_a, open(b, "r") as read_b:        
#             r1 = read_content(read_a.read())
#             r2 = read_content(read_b.read())
            
#             x = int(r1["total_sequences"])
#             y = int(r2["total_sequences"])
#             pairs[k] = x == y
    
#     return dg.AssetCheckResult(
#         description="Verify total sequences across R1 and R2",
#         passed=bool(all(pairs.values())),
#         metadata=pairs
#     )

############## RIBO-ANALYSIS

@dg.asset(
    deps=[fastqc_post],
    check_specs=[
        dg.AssetCheckSpec(
            name="ribo_analysis",
            description="Align paired-end reads to rRNA index",
            asset="rrna_mapping",
            blocking=False,
        )
    ],
    kinds={"docker"},
)
def rrna_mapping(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of bowtie2 tool"""
    result = docker_client.run(
        image="bowtie2",
        command=["python", "/scripts/rrna_mapping_bowtie2.py"],
        context=context,
        extras={
            "parallel_threads": 20,
        },
        container_kwargs={
            "auto_remove": True,
            "volumes": {
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "scripts"): {
                    "bind": "/scripts",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) 
                    / "data" 
                    / "output"
                    / "pre_processing"
                    / "umi_trimmed"
                    ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) 
                    / "data" 
                    / "output"
                    / "ribo_analysis"
                    / "index"
                    ): {
                    "bind": "/index",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "ribo_analysis"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )
    yield dg.AssetCheckResult(passed=True, check_name="no_name_yet")
    yield dg.Output(value=str(result.get_results()))



@dg.asset(
    deps=[rrna_mapping],
    check_specs=[
        dg.AssetCheckSpec(
            name="ribo_analysis",
            description="Extract read IDs from SAM file",
            asset="parse_sam_for_read_ids",
            blocking=False,
        )
    ],
    kinds={"duckdb"},
)
def parse_sam_for_read_ids(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
) -> Iterator[dg.Output[str]]:
    """Parse SAM file to extract read IDs"""

    input_folder = config.ribo_id_sam
    files_to_split = config.ribo_id_fastq
    clean_output_dir = config.ribo_id_clean
    rrna_output_dir = config.ribo_id_rrna
    
    stats = []
    
    for file in glob(f'{input_folder}/*.sam'):

        context.log.info(f"Parsing {file} for aligned read IDs...")
    
        duckdb.sql("""
            CREATE OR REPLACE TABLE rrna_ids AS
            SELECT column00 AS read_id
            FROM read_csv($file, 
                delim='\t', 
                header=false,strict_mode=false, 
                comment='@', ignore_errors=true)
            """,params={'file': file})
        rrna_count = duckdb.sql("SELECT COUNT(*) FROM rrna_ids").fetchone()[0]
        context.log.info(f"Loaded {rrna_count} unique rRNA IDs")

        # Create file paths
        sample_name = Path(file).stem
        clean_output_dir.mkdir(parents=True, exist_ok=True)
        rrna_output_dir.mkdir(parents=True, exist_ok=True)

        # Input file paths
        original_file_r1 =  files_to_split / f"{sample_name}_1.fq.gz"
        original_file_r2 =  files_to_split / f"{sample_name}_2.fq.gz"

        # Output file paths
        rrna_r1 = rrna_output_dir / f"{sample_name}_rRNA_R1.fastq.gz"
        rrna_r2 = rrna_output_dir / f"{sample_name}_rRNA_R2.fastq.gz"
        clean_r1 = clean_output_dir / f"{sample_name}_clean_R1.fastq.gz"
        clean_r2 = clean_output_dir / f"{sample_name}_clean_R2.fastq.gz"
        

        def split_fastq_file(input_file, output_clean, output_rrna):
            """Split a single FASTQ file into rRNA and clean files."""
            context.log.info(f"\n{'='*70}")
            context.log.info(f"Processing {input_file}")
            context.log.info('='*70)
            
            # Read and parse FASTQ file
            context.log.info("Reading FASTQ file...")
            duckdb.sql(f"""
                CREATE OR REPLACE TABLE fastq_all_lines AS
                SELECT 
                    ROW_NUMBER() OVER () - 1 AS line_num,
                    column0 AS line_content
                FROM read_csv('{input_file}', 
                            delim='\n',
                            header=false,
                            quote='',
                            columns={{'column0': 'VARCHAR'}})
            """)
            
            total_lines = duckdb.sql("SELECT COUNT(*) FROM fastq_all_lines").fetchone()[0]
            total_reads = total_lines // 4
            context.log.info(f"Read {total_lines} lines ({total_reads} reads)")
            
            # Extract headers and classify
            context.log.info("Classifying reads...")
            duckdb.sql("""
                CREATE OR REPLACE TABLE classified_records AS
                SELECT 
                    line_num,
                    line_num / 4 AS record_num,
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(line_content, '^@', ''),
                        '[/\\s].*$', ''
                    ) AS read_id,
                    CASE 
                        WHEN rr.read_id IS NOT NULL THEN 'rrna'
                        ELSE 'clean'
                    END AS category
                FROM fastq_all_lines
                LEFT JOIN rrna_ids rr 
                    ON REGEXP_REPLACE(
                        REGEXP_REPLACE(line_content, '^@', ''),
                        '[/\\s].*$', ''
                    ) = rr.read_id
                WHERE line_num % 4 = 0  -- Header lines only
            """)
            
            # Get counts
            rrna_reads = duckdb.sql("SELECT COUNT(*) FROM classified_records WHERE category = 'rrna'").fetchone()[0]
            clean_reads = duckdb.sql("SELECT COUNT(*) FROM classified_records WHERE category = 'clean'").fetchone()[0]
            
            context.log.info(f"  rRNA reads: {rrna_reads}")
            context.log.info(f"  Clean reads: {clean_reads}")
            
            # Export rRNA reads
            context.log.info(f"Writing {output_rrna}...")
            duckdb.sql(f"""
                COPY (
                    SELECT line_content
                    FROM fastq_all_lines
                    WHERE line_num / 4 IN (
                        SELECT record_num 
                        FROM classified_records 
                        WHERE category = 'rrna'
                    )
                    ORDER BY line_num
                ) TO '{output_rrna}' (FORMAT CSV, DELIMITER '\n', HEADER false, QUOTE '')
            """)
            
            # Compress with gzip
            subprocess.run(['gzip', '-f', output_rrna], check=True)
            
            # Export clean reads
            context.log.info(f"Writing {output_clean}...")
            duckdb.sql(f"""
                COPY (
                    SELECT line_content
                    FROM fastq_all_lines
                    WHERE line_num / 4 IN (
                        SELECT record_num 
                        FROM classified_records 
                        WHERE category = 'clean'
                    )
                    ORDER BY line_num
                ) TO '{output_clean}' (FORMAT CSV, DELIMITER '\n', HEADER false, QUOTE '')
            """)
            
            # Compress with gzip
            subprocess.run(['gzip', '-f', output_clean], check=True)
            
            return total_reads, rrna_reads, clean_reads

        context.log.info(f"Splitting FASTQ files for sample {sample_name}...")

        # Process both files
        total_reads1, rrna1, clean1 = split_fastq_file(original_file_r1, clean_r1, rrna_r1)
        total_reads2, rrna2, clean2 = split_fastq_file(original_file_r2, clean_r2, rrna_r2)

        # Verification
        context.log.info("\n" + "="*70)
        context.log.info("VERIFICATION")
        context.log.info("="*70)

        if total_reads1 != total_reads2:
            context.log.info("✗ ERROR: Paired-end files have different total reads!")
            context.log.info(f"  - File 1: {total_reads1} total reads")
            context.log.info(f"  - File 2: {total_reads2} total reads")
        else: 
            context.log.info("✓ SUCCESS: Paired-end files have the same total reads!")
            total_reads = total_reads1
        if rrna1 == rrna2 and clean1 == clean2:
            context.log.info("✓ SUCCESS: Paired-end files are consistent!")
            context.log.info(f"  - rRNA reads: {rrna1} in each file")
            context.log.info(f"  - Clean reads: {clean1} in each file")
        else:
            context.log.info("✗ WARNING: Paired-end files have different counts!")
            context.log.info(f"  - File 1: {rrna1} rRNA, {clean1} clean")
            context.log.info(f"  - File 2: {rrna2} rRNA, {clean2} clean")

        context.log.info("\nOutput files created:")
        context.log.info(Path(clean_r1).name)
        context.log.info(Path(rrna_r1).name)
        context.log.info(Path(clean_r2).name)
        context.log.info(Path(rrna_r2).name)
        context.log.info("\nDone!")

        # Statistics
        stats_dict = {
            'sample': sample_name,
            'total_reads': total_reads,
            'rrna_reads_1': rrna1,
            'rrna_reads_2': rrna2,
            'clean_reads_1': clean1,
            'clean_reads_2': clean2,
            'rrna_proportion_1': rrna1/total_reads*100,
            'rrna_proportion_2': rrna2/total_reads*100,
            'clean_reads_proportion_1': clean1/total_reads*100,
            'clean_reads_proportion_2': clean2/total_reads*100,
        }

        stats.append(stats_dict)
    # very long uses only one cpu at the time - useless
    #yield dg.AssetCheckResult(passed=True, check_name="no_name_yet")
    yield dg.Output(value=stats, metadata={"dagster/num_rows": len(stats)})


@dg.asset(
    deps=[parse_sam_for_read_ids],
    check_specs=[
        dg.AssetCheckSpec(
            name="ribo_analysis",
            description="Check stats",
            asset="stats_ribo_analysis",
            blocking=False,
        )
    ],
    kinds={"python"},
)
def stats_ribo_analysis(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    parse_sam_for_read_ids : List[dict],
) -> Iterator[dg.Output[str]]:
    """validate the rRNA content on each files"""

    map(valfc(lambda x: x.startswith('S18')), parse_sam_for_read_ids)
    map(valfc(lambda x: x.startswith('S23')), parse_sam_for_read_ids)
    map(valfc(lambda x: x.startswith('S33')), parse_sam_for_read_ids)
    map(valfc(lambda x: x.startswith('S38')), parse_sam_for_read_ids)

    out = 'to be determined'

    #yield dg.AssetCheckResult(passed=True, check_name="no_name_yet")
    yield dg.Output(value=out)



#################### END RIBO - ANALYSIS

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
                    / "output"
                    / "prokka_output"
                ): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                    / "output"
                    / "indexes"
                ): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                    / "output"
                    / "processed_fastq"
                    / "gz"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "indexes"
                ): {
                    "bind": "/indexes",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outpu"): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))


@dg.asset(
    deps=[umitools_runner],
    # check_specs=[
    #     dg.AssetCheckSpec(
    #         name="file_count",
    #         description="create kallisto indexes",
    #         asset="kallisto_indexes",
    #         blocking=False,
    #     )
    # ],
    kinds={"docker"},
)
def kallisto_indexes(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of kallisto tool"""
    result = docker_client.run(
        image="kallisto",
        command=["python", "/scripts/kallisto_index.py"],
        context=context,
        extras={
           "parallel_threads": 20,
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
                    / "output"
                    / "annotation"
                    / "bakta_output"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "mapping"
                    / "bact_gene_comp"
                ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    # yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))



@dg.asset(
    deps=[kallisto_indexes],
    # check_specs=[
    #     dg.AssetCheckSpec(
    #         name="file_count",
    #         description="Mapping complet",
    #         asset="kallisto_pseudo_mapping",
    #         blocking=False,
    #     )
    # ],
    kinds={"docker"},
)
def kallisto_pseudo_mapping(
    context: dg.AssetExecutionContext,
    config: RnaSequenceConfig,
    docker_client: PipesDockerClient,
) -> Iterator[dg.Output[str]]:
    """Docker execution of kallisto tool"""
    result = docker_client.run(
        image="kallisto",
        command=["python", "/scripts/kallisto.py"],
        context=context,
        extras={
           "parallel_threads": 20,
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
                    / "output"
                    / "pre_processing"
                    / "umi_trimmed"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "mapping"
                    / "bact_gene_comp"
                    / "kallisto_indexes"
                ): {
                    "bind": "/indexes",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "mapping"
                    / "bact_gene_comp"
                    ): {
                    "bind": "/outputs",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    #yield dg.AssetCheckResult(passed=True, check_name="file_count")

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
                    / "output"
                    / "bowtie2"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outpu"): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outpu5"): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                    / "output"
                    / "sorted_bam"
                ): {
                    "bind": "/inputs",
                    "mode": "ro",
                },
                str(
                    Path(os.getenv("RNA_SEQUENCE_HOME"))
                    / "data"
                    / "output"
                    / "gtf_files"
                ): {
                    "bind": "/references",
                    "mode": "ro",
                },
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "data" / "outpu"): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

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
                str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outpu5"): {
                    "bind": "/output",
                    "mode": "rw",
                },
            },
        },
    )

    # FIXME: use the glob instead of the listdir
    # files_in = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "inputs"))
    # files_out = os.listdir(str(Path(os.getenv("RNA_SEQUENCE_HOME")) / "outp2"))

    # _stems = compose(first, mc("split", "-"), at("stem"), Path)
    # _f_ins = list(map(_stems, files_in))
    # _f_outs = list(map(_stems, files_out))
    # complete = set(_f_ins).issubset(set(_f_outs))

    yield dg.AssetCheckResult(passed=True, check_name="file_count")

    yield dg.Output(value=str(result.get_results()))

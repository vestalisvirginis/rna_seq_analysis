import re
import subprocess
from pathlib import Path

from dagster_pipes import open_dagster_pipes
from toolz import compose, juxt
from toolz.curried import filter as cfilter
from toolz.curried import map as cmap

with open_dagster_pipes() as context:
    result = subprocess.run(["bowtie2", "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    context.log.info(str(version))
    # context.report_asset_materialization(metadata={"bowtie2_tools_version": version})

    # extras = context.extras
    # context.log.info(str(extras))
    # bc_pattern = context.get_extra("bc_pattern")
    parallel_threads = context.get_extra("parallel_threads")

    #######
    inputs = Path("/inputs")
    output_folder = Path("/outputs")
    result_path = output_folder / "bowtie2"
    result_path.mkdir(parents=True, exist_ok=True)

    _168_samples = ["S16", "S21", "S26", "S31", "S36", "S41", "S46", "S51", "S56"]
    _p9b1_samples = [
        "S17",
        "S22",
        "S27",
        "S32",
        "S37",
        "S42",
        "S47",
        "S52",
        "S57",
        "S18",
        "S23",
        "S28",
        "S33",
        "S38",
        "S43",
        "S48",
        "S53",
        "S58",
    ]
    _mb8b7_samples = [
        "S19",
        "S24",
        "S29",
        "S34",
        "S39",
        "S44",
        "S49",
        "S54",
        "S59",
        "S20",
        "S25",
        "S30",
        "S35",
        "S40",
        "S45",
        "S50",
        "S55",
        "S60",
    ]

    _get_gz_files = lambda x: x.glob("*.gz")
    _get_prefix = lambda x: re.split(r"_\d\.", x.name)[0]
    _is_168 = lambda x: any(x.startswith(s) for s in _168_samples)
    _is_p9b1 = lambda x: any(x.startswith(s) for s in _p9b1_samples)
    _is_mb8b7 = lambda x: any(x.startswith(s) for s in _mb8b7_samples)

    files = compose(set, cmap(_get_prefix))(list(_get_gz_files(inputs)))

    _168_files, _p9b1_files, _mb8b7_files = juxt(
        compose(list, cfilter(_is_168)),
        compose(list, cfilter(_is_p9b1)),
        compose(list, cfilter(_is_mb8b7)),
    )(files)

    # get parameters for bowtie2
    _1 = lambda x: f"{inputs}/{x}_1.fq.gz"
    _2 = lambda x: f"{inputs}/{x}_2.fq.gz"
    # _get_param = lambda x: f"'{"', '".join(x)}'"
    # _get_param = lambda x: " ".join(str(x))
    _get_param = lambda x: ",".join(x)

    def get_param(files: list) -> tuple:
        # return juxt(compose(_get_param, list, cmap(_1)), compose(_get_param, list, cmap(_2)))(files)
        return juxt(
            compose(_get_param, list, cmap(_1)), compose(_get_param, list, cmap(_2))
        )(files)

    context.log.info("BowTie2: Started")

    if _168_files:
        context.log.info(f"Processing 168 files: {len(_168_files)} files")

        _param_1, _param_2 = get_param(_168_files)
        cmd_168 = [
            "bowtie2",
            "-x",
            "/indexes/168.fasta",
            "-1",
            _param_1,
            "-2",
            _param_2,
            "-S",
            f"{result_path}/168.sam",
            "--threads",
            str(parallel_threads),
            "--end-to-end",
        ]
        output_168 = subprocess.run(cmd_168, capture_output=True, text=True)

        # log_168 = output_168.stdout.strip()
        # context.log.info(str(log_168))
        context.log.info("Process complete")

    if _p9b1_files:
        context.log.info(f"Processing P9B1 files: {len(_p9b1_files)} files")

        _param_1, _param_2 = get_param(_p9b1_files)
        cmd_p9b1 = [
            "bowtie2",
            "-x",
            "/indexes/p9b1_lys_spbeta.fasta",
            "-1",
            _param_1,
            "-2",
            _param_2,
            "-S",
            f"{result_path}/p9b1.sam",
            "--threads",
            str(parallel_threads),
            "--end-to-end",
        ]
        output_p9b1 = subprocess.run(cmd_p9b1, capture_output=True, text=True)

        # log_p9b1 = output_p9b1.stdout.strip()
        # context.log.info(str(log_p9b1))
        context.log.info("Process complete")

    if _mb8b7_files:
        context.log.info(f"Processing MB8_B7 files: {len(_mb8b7_files)} files")

        _param_1, _param_2 = get_param(_mb8b7_files)
        cmd_mb8b7 = [
            "bowtie2",
            "-x",
            "/indexes/mb8b7.fasta",
            "-1",
            _param_1,
            "-2",
            _param_2,
            "-S",
            f"{result_path}/mb8b7.sam",
            "--threads",
            str(parallel_threads),
            "--end-to-end",
        ]
        output_mb8b7 = subprocess.run(cmd_mb8b7, capture_output=True, text=True)

        # log_mb8b7 = output_mb8b7.stdout.strip()
        # context.log.info(str(output_mb8b7))
        context.log.info("Process complete")

    context.log.info("BowTie2: Completed")

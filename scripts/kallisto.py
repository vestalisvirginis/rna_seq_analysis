import re
import subprocess
from pathlib import Path

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
    indexes = Path("/indexes")
    output_folder = Path("/outputs")
    result_path = output_folder / "kallisto"
    result_path.mkdir(parents=True, exist_ok=True)
    _168_path = result_path / "168"
    _168_path.mkdir(parents=True, exist_ok=True)
    _p9b1_path = result_path / "p9b1"
    _p9b1_path.mkdir(parents=True, exist_ok=True)
    _mb8b7_path = result_path / "mb8b7"
    _mb8b7_path.mkdir(parents=True, exist_ok=True)

    context.log.info("Sort input files")

    context.log.info(f"check input files: {list(inputs.glob('*.gz'))}")
    context.log.info(f"check index files: {list(indexes.glob('*'))}")

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
    _pairs = lambda x: (f'{x}_1.fq.gz', f'{x}_2.fq.gz')

    files = compose(set, cmap(_get_prefix))(list(_get_gz_files(inputs)))

    _168_files, _p9b1_files, _mb8b7_files = juxt(
        compose(list, cmap(_pairs), list, cfilter(_is_168)),
        compose(list, cmap(_pairs), list, cfilter(_is_p9b1)),
        compose(list, cmap(_pairs), list, cfilter(_is_mb8b7)),
    )(files)

    context.log.info("kallisto: Started")

    for file in _168_files:
        name = str(Path(Path(file[0]).stem).stem).rstrip('_1')
        context.log.info(f"Processing 168 files: {name} files")
        context.log.info(f"Processing 168 files: {inputs}/{file[0]} and {inputs}/{file[1]} files")

        cmd = [
            "kallisto",
            "quant",
            "-i",
            f"{indexes}/168.index",
            "-o",
            f"{_168_path}/{name}",
            "-t",
            "20",
            f"{inputs}/{file[0]}",
            f"{inputs}/{file[1]}",
        ]

        context.log.info(f"Running command: {' '.join(cmd)}")
        output = subprocess.run(cmd, capture_output=True, text=True)

        context.log.info(f"File : {name}... Process completed")

    for file in _p9b1_files:
        name = str(Path(Path(file[0]).stem).stem).rstrip('_1')
        context.log.info(f"Processing p9b1 files: {name} files")
        context.log.info(f"Processing p9b1 files: {inputs}/{file[0]} and {inputs}/{file[1]} files")


        cmd = [
            "kallisto",
            "quant",
            "-i",
            f"{indexes}/p9b1_lys_spbeta.index",
            "-o",
            f"{_p9b1_path}/{name}",
            "-t",
            "20",
            f"{inputs}/{file[0]}",
            f"{inputs}/{file[1]}",
        ]

        context.log.info(f"Running command: {' '.join(cmd)}")
        output = subprocess.run(cmd, capture_output=True, text=True)

        context.log.info(f"File : {name}... Process completed")

    
    for file in _mb8b7_files:
        name = str(Path(Path(file[0]).stem).stem).rstrip('_1')
        context.log.info(f"Processing mb8b7 files: {name} files")
        context.log.info(f"Processing mb8b7 files: {inputs}/{file[0]} and {inputs}/{file[1]} files")

        cmd = [
            "kallisto",
            "quant",
            "-i",
            f"{indexes}/mb8b7.index",
            "-o",
            f"{_mb8b7_path}/{name}",
            "-t",
            "20",
            f"{inputs}/{file[0]}",
            f"{inputs}/{file[1]}",
        ]
        context.log.info(f"Running command: {' '.join(cmd)}")
        output = subprocess.run(cmd, capture_output=True, text=True)
        
        context.log.info(f"File : {name}... Process completed")
    

    context.log.info("kallisto: Completed")
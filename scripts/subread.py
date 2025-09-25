import subprocess
from glob import glob
from pathlib import Path

from dagster_pipes import open_dagster_pipes

with open_dagster_pipes() as context:
    result = subprocess.run(
        ["featureCounts", "-v"],
        capture_output=True,
        text=True,
    )
    version = result.stdout.strip()
    version_err = result.stderr.strip()
    # context.log.info(str(version))
    context.log.info(str(version_err))
    # context.report_asset_materialization(metadata={"bowtie2_tools_version": version})

    # extras = context.extras
    # context.log.info(str(extras))
    # bc_pattern = context.get_extra("bc_pattern")
    # parallel_threads = context.get_extra("parallel_threads")

    ins = Path("/inputs")
    refs = Path("/references")
    outs = Path("/outputs") / "featurecounts"
    outs.mkdir(parents=True, exist_ok=True)

    context.log.info("FeatureCounts: Started")

    context.log.info("Processing 168")
    cmd_168 = [
        "featureCounts",
        "-p",
        "-O",
        "-T",
        "40",
        "-a",
        f"{refs}/168.gtf",
        "-t",
        "CDS",
        "-g",
        "transcript_id",
        "-o",
        f"{outs}/168_featureCounts.txt",
        f"{ins}/168.bam.sorted.bam",
    ]
    subprocess.run(cmd_168, capture_output=True, text=True)
    context.log.info("168: Process completed")

    context.log.info("Processing p9b1")
    cmd_p9b1 = [
        "featureCounts",
        "-p",
        "-O",
        "-T",
        "40",
        "-a",
        f"{refs}/p9b1.gtf",
        "-t",
        "CDS",
        "-g",
        "transcript_id",
        "-o",
        f"{outs}/p9b1_featureCounts.txt",
        f"{ins}/p9b1.bam.sorted.bam",
    ]
    subprocess.run(cmd_p9b1, capture_output=True, text=True)
    context.log.info("p9b1: Process completed")

    context.log.info("Processing mb8b7")
    cmd_mb8b7 = [
        "featureCounts",
        "-p",
        "-O",
        "-T",
        "40",
        "-a",
        f"{refs}/mb8b7.gtf",
        "-t",
        "CDS",
        "-g",
        "transcript_id",
        "-o",
        f"{outs}/mb8b7_featureCounts.txt",
        f"{ins}/mb8b7.bam.sorted.bam",
    ]
    subprocess.run(cmd_mb8b7, capture_output=True, text=True)
    context.log.info("mb8b7: Process completed")

    # find_proc = subprocess.Popen(
    #     ["find", "/inputs", "-name", "*.fasta"], stdout=subprocess.PIPE
    # )
    # parallel_cmd = [
    #     "parallel",
    #     "-j",
    #     str(parallel_threads),
    #     f"bowtie2-build -f {{}} /outputs/{{/}}",
    # ]
    # output = subprocess.run(
    #     parallel_cmd, stdin=find_proc.stdout, capture_output=True, text=True
    # )
    # find_proc.stdout.close()

    # output = subprocess.run(command, capture_output=True, text=True)
    context.log.info("FeatureCounts: Completed")

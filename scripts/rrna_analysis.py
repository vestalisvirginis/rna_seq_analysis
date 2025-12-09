#!/usr/bin/env python3
"""
rRNA Filtering Pipeline for Paired-End Reads
Filters reads against known rRNA sequences and generates separate output files
"""

import gzip
import subprocess
import os
import json
from pathlib import Path
from collections import defaultdict
import argparse


# STEP 1: Index rRNA sequences with Bowtie2
# Libraries: subprocess (standard library)
# Expected outcome:
# - Bowtie2 index files (.bt2) for rRNA sequences
# - Index ready for alignment

def index_rrna_sequences(rrna_fasta, index_prefix):
    """
    Create Bowtie2 index from rRNA sequences.
    
    Args:
        rrna_fasta: Path to FASTA file with rRNA sequences
        index_prefix: Prefix for index files
    """
    print(f"Building Bowtie2 index for {rrna_fasta}...")
    cmd = ["bowtie2-build", rrna_fasta, index_prefix]
    subprocess.run(cmd, check=True)
    print(f"Index created: {index_prefix}")


# STEP 2: Align paired-end reads to rRNA index
# Libraries: subprocess
# Expected outcome:
# - SAM file with alignment results
# - Each read pair classified as aligned or unaligned to rRNA

def align_to_rrna(r1_fastq, r2_fastq, index_prefix, output_sam, threads=4):
    """
    Align paired-end reads to rRNA index using Bowtie2.
    
    Args:
        r1_fastq: Read 1 FASTQ file
        r2_fastq: Read 2 FASTQ file
        index_prefix: Bowtie2 index prefix
        output_sam: Output SAM file
        threads: Number of threads
    """
    print(f"Aligning {r1_fastq} and {r2_fastq} to rRNA index...")
    cmd = [
        "bowtie2",
        "-x", index_prefix,
        "-1", r1_fastq,
        "-2", r2_fastq,
        "-S", output_sam,
        "--threads", str(threads),
        "--no-unal"  # Only output aligned reads
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(result.stderr)  # Bowtie2 reports stats to stderr
    return output_sam


# STEP 3: Parse SAM file to extract read IDs
# Libraries: Standard library (file I/O)
# Expected outcome:
# - Set of read IDs that aligned to rRNA
# - Statistics on alignment rate

def parse_sam_for_read_ids(sam_file):
    """
    Extract read IDs from SAM file.
    
    Args:
        sam_file: Path to SAM file
        
    Returns:
        Set of read IDs that aligned to rRNA
    """
    print(f"Parsing {sam_file} for aligned read IDs...")
    aligned_ids = set()
    total_alignments = 0
    
    with open(sam_file, 'r') as f:
        for line in f:
            if line.startswith('@'):
                continue
            fields = line.strip().split('\t')
            read_id = fields[0]
            aligned_ids.add(read_id)
            total_alignments += 1
    
    print(f"Found {len(aligned_ids)} unique read pairs aligned to rRNA")
    print(f"Total alignment records: {total_alignments}")
    return aligned_ids


# STEP 4: Split FASTQ files based on rRNA alignment
# Libraries: gzip (standard library)
# Expected outcome:
# - FASTQ files with reads matching rRNA (R1 and R2)
# - FASTQ files with reads NOT matching rRNA (R1 and R2)
# - Statistics report (JSON format)

def split_fastq_by_rrna(r1_fastq, r2_fastq, aligned_ids, output_dir, sample_name):
    """
    Split paired-end FASTQ files into rRNA-matching and non-matching.
    
    Args:
        r1_fastq: Read 1 FASTQ file
        r2_fastq: Read 2 FASTQ file
        aligned_ids: Set of read IDs aligned to rRNA
        output_dir: Output directory
        sample_name: Sample name for output files
        
    Returns:
        Dictionary with file paths and statistics
    """
    print(f"Splitting FASTQ files for sample {sample_name}...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output file paths
    rrna_r1 = output_dir / f"{sample_name}_rRNA_R1.fastq.gz"
    rrna_r2 = output_dir / f"{sample_name}_rRNA_R2.fastq.gz"
    non_rrna_r1 = output_dir / f"{sample_name}_non_rRNA_R1.fastq.gz"
    non_rrna_r2 = output_dir / f"{sample_name}_non_rRNA_R2.fastq.gz"
    
    # Statistics
    stats = {
        'sample': sample_name,
        'total_reads': 0,
        'rrna_reads': 0,
        'non_rrna_reads': 0,
        'rrna_proportion': 0.0
    }
    
    # Process both read files simultaneously
    open_func = gzip.open if r1_fastq.endswith('.gz') else open
    
    with open_func(r1_fastq, 'rt') as f1_in, \
         open_func(r2_fastq, 'rt') as f2_in, \
         gzip.open(rrna_r1, 'wt') as f1_rrna, \
         gzip.open(rrna_r2, 'wt') as f2_rrna, \
         gzip.open(non_rrna_r1, 'wt') as f1_non, \
         gzip.open(non_rrna_r2, 'wt') as f2_non:
        
        while True:
            # Read 4 lines from each file (one FASTQ record)
            r1_lines = [f1_in.readline() for _ in range(4)]
            r2_lines = [f2_in.readline() for _ in range(4)]
            
            # Check if we've reached end of file
            if not r1_lines[0] or not r2_lines[0]:
                break
            
            # Extract read ID (remove @ and /1 or /2 suffix if present)
            read_id = r1_lines[0].strip().split()[0][1:]
            if read_id.endswith('/1') or read_id.endswith('/2'):
                read_id = read_id[:-2]
            
            stats['total_reads'] += 1
            
            # Write to appropriate files
            if read_id in aligned_ids:
                f1_rrna.writelines(r1_lines)
                f2_rrna.writelines(r2_lines)
                stats['rrna_reads'] += 1
            else:
                f1_non.writelines(r1_lines)
                f2_non.writelines(r2_lines)
                stats['non_rrna_reads'] += 1
    
    # Calculate proportion
    if stats['total_reads'] > 0:
        stats['rrna_proportion'] = stats['rrna_reads'] / stats['total_reads']
    
    print(f"Sample {sample_name}:")
    print(f"  Total reads: {stats['total_reads']}")
    print(f"  rRNA reads: {stats['rrna_reads']} ({stats['rrna_proportion']*100:.2f}%)")
    print(f"  Non-rRNA reads: {stats['non_rrna_reads']}")
    
    return {
        'stats': stats,
        'rrna_r1': str(rrna_r1),
        'rrna_r2': str(rrna_r2),
        'non_rrna_r1': str(non_rrna_r1),
        'non_rrna_r2': str(non_rrna_r2)
    }


# STEP 5: Process multiple samples and generate summary report
# Libraries: json (standard library), collections.defaultdict
# Expected outcome:
# - All samples processed
# - Summary JSON file with statistics for all samples
# - Comparison metrics for treated vs untreated samples

def process_samples(sample_list, rrna_fasta, output_base_dir, threads=4):
    """
    Process multiple samples through the pipeline.
    
    Args:
        sample_list: List of dicts with 'name', 'r1', 'r2', 'treated' keys
        rrna_fasta: Path to rRNA FASTA file
        output_base_dir: Base output directory
        threads: Number of threads for alignment
        
    Returns:
        Dictionary with all results and statistics
    """
    output_base_dir = Path(output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Create rRNA index
    index_dir = output_base_dir / "rrna_index"
    index_dir.mkdir(exist_ok=True)
    index_prefix = str(index_dir / "rrna_index")
    
    if not Path(f"{index_prefix}.1.bt2").exists():
        index_rrna_sequences(rrna_fasta, index_prefix)
    else:
        print(f"Using existing index: {index_prefix}")
    
    all_results = []
    
    # Process each sample
    for sample in sample_list:
        sample_name = sample['name']
        r1_fastq = sample['r1']
        r2_fastq = sample['r2']
        treated = sample.get('treated', False)
        
        print(f"\n{'='*60}")
        print(f"Processing sample: {sample_name}")
        print(f"Treated: {treated}")
        print(f"{'='*60}")
        
        # Create sample-specific directory
        sample_dir = output_base_dir / sample_name
        sample_dir.mkdir(exist_ok=True)
        
        # Step 2: Align to rRNA
        sam_file = sample_dir / f"{sample_name}_rrna_alignment.sam"
        align_to_rrna(r1_fastq, r2_fastq, index_prefix, str(sam_file), threads)
        
        # Step 3: Parse SAM for read IDs
        aligned_ids = parse_sam_for_read_ids(str(sam_file))
        
        # Step 4: Split FASTQ files
        result = split_fastq_by_rrna(
            r1_fastq, r2_fastq, aligned_ids, 
            sample_dir, sample_name
        )
        result['stats']['treated'] = treated
        all_results.append(result)
    
    # Step 5: Generate summary report
    summary_file = output_base_dir / "rrna_analysis_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    # Compare treated vs untreated
    treated_stats = [r['stats'] for r in all_results if r['stats']['treated']]
    untreated_stats = [r['stats'] for r in all_results if not r['stats']['treated']]
    
    if treated_stats:
        avg_treated = sum(s['rrna_proportion'] for s in treated_stats) / len(treated_stats)
        print(f"Treated samples (n={len(treated_stats)}): {avg_treated*100:.2f}% rRNA")
    
    if untreated_stats:
        avg_untreated = sum(s['rrna_proportion'] for s in untreated_stats) / len(untreated_stats)
        print(f"Untreated samples (n={len(untreated_stats)}): {avg_untreated*100:.2f}% rRNA")
    
    if treated_stats and untreated_stats:
        reduction = ((avg_untreated - avg_treated) / avg_untreated) * 100
        print(f"rRNA depletion efficiency: {reduction:.2f}%")
    
    print(f"\nSummary saved to: {summary_file}")
    
    return all_results


# Main execution
def main():
    parser = argparse.ArgumentParser(
        description='rRNA filtering pipeline for paired-end reads'
    )
    parser.add_argument('--rrna-fasta', required=True,
                        help='FASTA file with rRNA sequences')
    parser.add_argument('--sample-sheet', required=True,
                        help='JSON file with sample information')
    parser.add_argument('--output-dir', default='rrna_analysis',
                        help='Output directory')
    parser.add_argument('--threads', type=int, default=4,
                        help='Number of threads')
    
    args = parser.parse_args()
    
    # Load sample sheet
    # Expected format: [{"name": "sample1", "r1": "path/to/R1.fastq.gz", 
    #                    "r2": "path/to/R2.fastq.gz", "treated": true}, ...]
    with open(args.sample_sheet, 'r') as f:
        samples = json.load(f)
    
    # Run pipeline
    process_samples(samples, args.rrna_fasta, args.output_dir, args.threads)


if __name__ == '__main__':
    main()
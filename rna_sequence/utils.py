from Bio import SeqIO

def split_by_motif(fasta_file, motif):
    """Split sequences by motif - works with any line length"""
    
    results = []
    
    for record in SeqIO.parse(fasta_file, "fasta"):
        seq_str = str(record.seq)
        
        # Find first and second occurrence of motif
        start = seq_str.find(motif)
        if start == -1:
            print(f"No motif found in {record.id}")
            continue
            
        end = seq_str.find(motif, start + len(motif))
        if end == -1:
            print(f"Only one motif found in {record.id}")
            continue
        
        print(f"Found motifs in {record.id} at positions {start} and {end}")
        
        # Extract between motifs (including motifs)
        between_seq = seq_str[start:end + len(motif)]
        
        # Extract without between region (bacterial genome)
        without_seq = seq_str[:start] + seq_str[end + len(motif):]
        
        results.append({
            'id': record.id,
            'full_length': len(seq_str),
            'prophage': between_seq,
            'prophage_length': len(between_seq),
            'bacterial': without_seq,
            'bacterial_length': len(without_seq)
        })
    
    return results

# Usage
results = split_by_motif(
    "../rna-sequence/temp/data/references/mb8b7.fasta",
    "ACAGATAAAGCTGTAT"
)

for r in results:
    print(f"\n{r['id']}:")
    print(f"  Full genome: {r['full_length']:,} bp")
    print(f"  Prophage: {r['prophage_length']:,} bp")
    print(f"  Bacterial: {r['bacterial_length']:,} bp")
    
    # Save to files
    with open(f"{r['id']}_prophage.fasta", 'w') as f:
        f.write(f">{r['id']}_prophage\n{r['prophage']}\n")
    
    with open(f"{r['id']}_bacterial.fasta", 'w') as f:
        f.write(f">{r['id']}_bacterial\n{r['bacterial']}\n")
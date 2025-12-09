#docker run -v /mnt/data/projects/90_databases/bakta_db:/db --entrypoint /bin/bash oschwengers/bakta:latest -c "bakta_db download --output /db --type full"


#sudo docker run --rm -v /mnt/data/projects/90_databases/bakta_db/db/:/db -v /mnt/data/projects/3_rnaseq/3_analysis_pipeline/rna_seq_analysis/temp/data/output_bakta/:/outputs -v /mnt/data/projects/3_rnaseq/3_analysis_pipeline/rna_seq_analysis/temp/data/input/:/inputs --entrypoint /bin/bash oschwengers/bakta:latest -c "bakta --db /db --verbose --output /outputs/p9b1_lys_spbeta --prefix p9b1_lys_spbeta --locus-tag p9b1 --genus Bacillus --species subtilis --strain P9_B1 --complete --gram + --replicons /inputs/replicon_files/p9b1_replicon.tsv --threads 16 /inputs/fasta/p9b1_lys_spbeta.fasta"

#sudo docker run --rm -v /mnt/data/projects/90_databases/bakta_db/db/:/db -v /mnt/data/projects/3_rnaseq/3_analysis_pipeline/rna_seq_analysis/temp/data/output_bakta/:/outputs -v /mnt/data/projects/3_rnaseq/3_analysis_pipeline/rna_seq_analysis/temp/data/input/:/inputs --entrypoint /bin/bash oschwengers/bakta:latest -c "bakta --db /db --verbose --output /outputs/mb8b7 --prefix mb8b7 --locus-tag mb8b7 --genus Bacillus --species subtilis --strain MB8_B7 --complete --gram + --replicons /inputs/replicon_files/mb8b7_replicon.tsv --threads 16 /inputs/fasta/mb8b7.fasta"








#NZ_CP045821.1:
##  Full genome: 4,191,568 bp
#  Prophage: 136,191 bp
#  Bacterial: 4,055,377 bp

#NC_000964.3:
#  Full genome: 4,215,606 bp
#  Prophage: 134,402 bp
##  Bacterial: 4,081,204 bp

#P9_B1_lys_SPbeta:
#  Full genome: 4,192,825 bp
#  Prophage: 129,239 bp
#  Bacterial: 4,063,586 bp
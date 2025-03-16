#!/bin/bash

# Create a raw files directory to untar files
mkdir -p temp/raw_files
# Extract all .tar files in the user_data directory
find temp  -name "*.tar" -type f -exec tar -xvf {} -C temp/raw_files \; 


# Find MD5 files and store unique directories in an array
mapfile -t unique_dirs < <(find temp -type f -name '*.txt' -exec dirname {} \; | sort -u)

# Create an array to store validated files
validated_files=()

# Loop through each unique directory
for dir in "${unique_dirs[@]}"; do 
  #echo "Processing directory: $dir"
  pushd "$dir" || continue
  while IFS=: read -r filename result; do 
    if [[ $result == *"OK" ]]; then 
      if [[ ! " ${validated_files[@]} " =~ " ${dir}/${filename} " ]]; then
        validated_files+=("$dir/$filename")
      fi
    fi
  done < <(md5sum -c MD5.txt)
  popd || exit
done


# Print validated files
echo "Successfully validated files:"
printf '%s\n' "${validated_files[@]}"

# Save validated file paths to a file
printf '%s\n' "${validated_files[@]}" > validated_files.txt

# Create destination directory for 
mkdir -p temp/gz_files

# Extract .gz files and copy them
while IFS= read -r line; do
    if [[ $line == *.gz ]]; then
        # Create the destination directory structure
        #dir_name=$(dirname "temp/gz_files/${line#temp/raw_files/}")
       # mkdir -p "$dir_name"
        # Extract just the filename without path
        filename=$(basename "$line")
        # Copy the file, preserving directory structure
        cp "$line" "temp/gz_files/$filename"
    fi
done < temp/validated_files.txt

# Verify the copy
echo "Copied files:"
find temp/gz_files -name "*.gz" -type f


# Fastqc
mkdir temp/fastqc
find temp/gz_files/*.gz -exec fastqc -o temp/fastqc/ {} \;

# UMI
mkdir temp/umi_processed
#umi_tools extract --stdin=temp/gz_files/wt_1_MKDL250000598-1A_HV7W7DSXC_L3_2.fq.gz --bc-pattern=NNNNNNNNNNNNNNNNNNNNNNNNNNNNNXXXXXXXXNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN --log=processed.log --stdout temp/umi_processed/wt_1_MKDL250000598-1A_HV7W7DSXC_L3_2.fq.gz

find temp/gz_files/*.gz -exec umi_tools extract --bc-pattern=NNNNCCCCNNN --log=temp/umi_processed/processed.log --stdout=temp/umi_processed/processed_{} {} \;


for i in $(find temp/gz_files/*.gz ); do j=$(echo $i | cut -d"/" -f3); umi_tools extract --bc-pattern=NNNNCCCCNNN --log=temp/umi_processed/processed.log --stdout="temp/umi_processed/processed_$j" --stdin="$i"; done

umi_tools extract [OPTIONS] -p PATTERN [-I IN_FASTQ[.gz]] [-S OUT_FASTQ[.gz]]

umi_tools extract -p NNNNCCCCNNN -I temp/gz_files/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz -L temp/umi_processed/log/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.log -S temp/umi_processed/fasta/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz

#  working command
umi_tools extract -p NNNNCCCCNNN -I temp/gz_files/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz -L temp/umi_processed/log/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.log -S temp/umi_processed/fasta/spbeta_1_MKDL250000598-1A_HV7W7DSXC_L3_1.fq.gz


for i in $(find temp/gz_files/*.gz ); do j=$(echo $i | cut -d"/" -f3); umi_tools extract -p NNNNCCCCNNN -I "temp/gz_files/$j" -L "temp/umi_processed/log/$j.log" -S "temp/umi_processed/fasta/$j"; done


mkdir trimmed
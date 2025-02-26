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

find temp/gz_files/*.gz -exec umi_tools extract --bc-pattern=NNNNNNNNNNNNNNNNNNNNNNNNNNNNNXXXXXXXXNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN --log=processed.log {} \;

mkdir trimmed
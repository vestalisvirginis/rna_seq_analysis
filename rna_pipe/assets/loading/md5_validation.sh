#!/bin/bash

# Find MD5 files and store unique directories in an array
mapfile -t unique_dirs < <(find $RAW_DATA -type f -name '*.txt' -exec dirname {} \; | sort -u)

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
printf '%s\n' "${validated_files[@]}" > ${RAW_DATA}/md5_validated_files.txt

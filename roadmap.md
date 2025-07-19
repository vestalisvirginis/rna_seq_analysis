apt update & apt upgrade

# Install FastQC

apt update && apt install -y \
    openjdk-11-jre \
    wget \
    unzip && \
    cd /opt && \
    wget https://www.bioinformatics.babraham.ac.uk/projects/fastqc/fastqc_v0.12.1.zip && \
    unzip fastqc_v0.12.1.zip && \
    chmod +x FastQC/fastqc && \
    ln -s /opt/FastQC/fastqc /usr/local/bin/fastqc


Needed packeges???
    libtbbmalloc2
    ca-certificates \
    zlib1g-dev \
    libncurses5 \
    libncursesw5 \

cd /opt
git clone --recurse-submodules https://github.com/BenLangmead/bowtie2.git
cd bowtie2
make -j$(nproc)
PATH="/opt/bowtie2:$PATH"
# to test if it works
bowtie2 --version



cd isa-l            # Move into the source directory
./autogen.sh        # Generate the configure script
./configure         # Configure the build system for your platform (ARM64 supported)
make -j$(nproc)     # Compile using all CPU cores
sudo make install   # Install the library system-wide
sudo ldconfig       # Refresh dynamic linker run-time bindings (required)

cd isa-l
./autogen.sh
./configure
make -j$(nproc)
make install
ldconfig


git clone https://github.com/OpenGene/fastp.git

# Install ISAL from source
WORKDIR /opt
RUN git clone https://github.com/intel/isa-l.git && \
    cd isa-l && \
    ./autogen.sh && \
    ./configure && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Clone and build fastp
RUN git clone https://github.com/OpenGene/fastp.git /opt/fastp
WORKDIR /opt/fastp
RUN make -j$(nproc)

# Add fastp to PATH
ENV PATH="/opt/fastp:$PATH"

# Test
RUN fastp --version



# Install HTSlib (required for samtools)
RUN cd /opt && \
    curl -L https://github.com/samtools/htslib/releases/download/1.19.1/htslib-1.19.1.tar.bz2 | tar xj && \
    cd htslib-1.19.1 && \
    ./configure && make && make install

# Install Samtools
RUN cd /opt && \
    curl -L https://github.com/samtools/samtools/releases/download/1.19.1/samtools-1.19.1.tar.bz2 | tar xj && \
    cd samtools-1.19.1 && \
    ./configure && make && make install

# Install FADU 
mkdir -p /opt/julia
curl -L "https://julialang-s3.julialang.org/bin/linux/aarch64/1.9/julia-1.9.4-linux-aarch64.tar.gz" | \
    tar -xz -C /opt/julia --strip-components=1

git clone https://github.com/IGS/FADU.git
chmod +x /opt/FADU/fadu.jl

# Install featureCounts (via Subread)
RUN cd /opt && \
    curl -L https://downloads.sourceforge.net/project/subread/subread-2.0.6/subread-2.0.6-Linux-x86_64.tar.gz | tar xz && \
    cp subread-2.0.6-Linux-x86_64/bin/featureCounts /usr/local/bin/ && \
    chmod +x /usr/local/bin/featureCounts

# Clean up
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
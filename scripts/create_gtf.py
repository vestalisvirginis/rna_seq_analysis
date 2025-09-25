from functools import partial
from operator import attrgetter as at
from operator import eq, gt
from operator import methodcaller as mc

import polars as pl
from Bio import SeqIO
from Bio.Seq import translate
from toolz import compose, first, juxt
from toolz.curried import map as mapc


def genbank_to_piled_dataframe(filename: str):

    # Read file
    genome = SeqIO.read(filename, "genbank")

    # features
    qualifiers = (
        "gene",
        "locus_tag",
        "protein_id",
        "function",
        "product",
        "translation",
        "transl_table",
        "codon_start",
        "inference",
        "note",
    )
    location_attributes = ("start", "end", "strand")

    # annotations
    annotations_attributes = ("topology", "organism", "taxonomy")
    topology, organism, taxonomy = compose(
        juxt(map(lambda x: mc("get", x, None), annotations_attributes)),
        at("annotations"),
    )(genome)
    # topology, organism, taxonomy = compose(juxt(map(it, annotations_attributes)), at("annotations"))(genome)

    # ids
    id_attributes = ("id", "name", "description")
    id, name, description = juxt(map(at, id_attributes))(genome)

    # fn
    _impute_attributes = lambda x: mc("get", x, [""])

    _type_cds = compose(partial(eq, "CDS"), at("type"))
    _type_gene = compose(partial(eq, "gene"), at("type"))
    _type_r_rna = compose(partial(eq, "rRNA"), at("type"))
    _type_t_rna = compose(partial(eq, "tRNA"), at("type"))
    _type_misc_RNA = compose(partial(eq, "misc_RNA"), at("type"))

    # process cds features related information
    data_cds = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_cds, genome.features),
        )
    )
    data_cds_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_cds, genome.features),
        )
    )

    df_cds = pl.DataFrame(data_cds, schema=qualifiers)
    df_cds_pk = pl.DataFrame(data_cds_pk, schema=location_attributes)
    # cds_extract = list(
    #    map(lambda x: str(x.extract(genome.seq)), filter(_type_cds, genome.features))
    # )
    # df_cds_extract = pl.DataFrame(cds_extract, schema=["cds_extract"])
    # df_cds_translate = pl.DataFrame(map(partial(translate, stop_symbol="", table=11), cds_extract), schema=["translation_fn"])

    cds = (
        pl.concat(items=[df_cds, df_cds_pk], how="horizontal")
        .with_columns(pl.lit("CDS").alias("feature"))
        .with_columns(pl.lit("Protein coding").alias("gene_biotype"))
    )

    # process gene features related information
    data_gene = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_gene, genome.features),
        )
    )
    data_gene_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_gene, genome.features),
        )
    )

    df_gene = pl.DataFrame(data_gene, schema=qualifiers)
    df_gene_pk = pl.DataFrame(data_gene_pk, schema=location_attributes)
    # gene_extract = list(
    #    map(lambda x: str(x.extract(genome.seq)), filter(_type_gene, genome.features))
    # )
    # df_gene_translate = pl.DataFrame(
    #    map(partial(translate, stop_symbol="", table=11), gene_extract),
    #    schema=["translation_fn"],
    # )
    # df_gene_extract = pl.DataFrame(gene_extract, schema=["extract"])

    gene = pl.concat(
        items=[df_gene, df_gene_pk],
        how="horizontal",
    ).with_columns(pl.lit("gene").alias("feature"))

    data_r_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_r_rna, genome.features),
        )
    )
    data_r_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_r_rna, genome.features),
        )
    )
    df_r_rna = pl.DataFrame(data_r_rna, schema=qualifiers)
    df_r_rna_pk = pl.DataFrame(data_r_rna_pk, schema=location_attributes)
    r_rna = (
        pl.concat(
            items=[df_r_rna, df_r_rna_pk],
            how="horizontal",
        )
        .with_columns(pl.lit("rRNA").alias("feature"))
        .with_columns(pl.lit("rRNA").alias("gene_biotype"))
    )

    data_t_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_t_rna, genome.features),
        )
    )
    data_t_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_t_rna, genome.features),
        )
    )
    df_t_rna = pl.DataFrame(data_t_rna, schema=qualifiers)
    df_t_rna_pk = pl.DataFrame(data_t_rna_pk, schema=location_attributes)
    t_rna = (
        pl.concat(
            items=[df_t_rna, df_t_rna_pk],
            how="horizontal",
        )
        .with_columns(pl.lit("tRNA").alias("feature"))
        .with_columns(pl.lit("tRNA").alias("gene_biotype"))
    )

    data_misc_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_misc_RNA, genome.features),
        )
    )
    data_misc_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_misc_RNA, genome.features),
        )
    )
    df_misc_rna = pl.DataFrame(data_misc_rna, schema=qualifiers)
    df_misc_rna_pk = pl.DataFrame(data_misc_rna_pk, schema=location_attributes)
    misc_rna = (
        pl.concat(
            items=[df_misc_rna, df_misc_rna_pk],
            how="horizontal",
        )
        .with_columns(pl.lit("miscRNA").alias("feature"))
        .with_columns(pl.lit("miscRNA").alias("gene_biotype"))
    )

    # join all the dataframes
    CDS_COLUMNS = [
        "gene",
        "locus_tag",
        "protein_id",
        "function",
        "product",
        "translation",
        "transl_table",
        "codon_start",
        "start",
        "end",
        "strand",
        "inference",
        "note",
        "feature",
        "gene_biotype",
    ]
    GENE_COLUMNS = ["gene", "locus_tag", "extract", "translation_fn"]
    GENERIC_COLUMNS = [
        "id",
        "name",
        "description",
        "topology",
        "organism",
        "taxonomy",
        "filename",
    ]

    product = pl.concat(
        items=[
            cds.select(*[pl.col(c) for c in CDS_COLUMNS]),
            r_rna.select(*[pl.col(c) for c in CDS_COLUMNS]),
            t_rna.select(*[pl.col(c) for c in CDS_COLUMNS]),
            misc_rna.select(*[pl.col(c) for c in CDS_COLUMNS]),
        ],
        how="vertical",
    )

    sizes = gt(first(product.shape), 0), gt(first(gene.shape), 0)
    match sizes:
        case (True, True):
            df = product.join(
                other=gene.with_columns(pl.all().name.suffix("_gene")),
                on=["start", "end", "strand"],
                how="full",
                coalesce=True,
            )
        case (True, False):
            df = product.with_columns(
                *[pl.lit(None).alias(f"{c}_gene") for c in CDS_COLUMNS]
            )
        case (False, True):
            df = gene.with_columns(pl.all().name.suffix("_gene")).with_columns(
                *[pl.lit(None).alias(c) for c in CDS_COLUMNS]
            )

    df = df.with_columns(
        id=pl.lit(id),
        name=pl.lit(name),
        description=pl.lit(description),
        topology=pl.lit(topology),
        organism=pl.lit(organism),
        taxonomy=pl.lit(taxonomy),
        filename=pl.lit(filename),
    )

    return df


# Sample Polars DataFrame (already parsed from GenBank)
# Columns: seqname, source, feature, start, end, strand, gene_id, transcript_id, score, frame


def df_to_gtf(df: pl.DataFrame, output_path: str):
    # Ensure required fields exist or default them
    if "score" not in df.columns:
        df = df.with_columns(pl.lit(".").alias("score"))
    if "frame" not in df.columns:
        df = df.with_columns(pl.lit(".").alias("frame"))
    if "source" not in df.columns:
        df = df.with_columns(pl.lit("GenBank").alias("source"))

    # Construct GTF attribute field
    df = df.with_columns(
        [
            pl.format(
                'gene_id "{}"; transcript_id "{}"; gene_biotype "{}";',
                pl.col("gene"),
                pl.col("locus_tag"),
                pl.col("gene_biotype"),
            ).alias("attribute"),
            pl.when(pl.col("strand") == 1)
            .then(pl.lit("+"))
            .when(pl.col("strand") == -1)
            .then(pl.lit("-"))
            .otherwise(pl.lit("."))
            .alias("strand"),
        ]
    )

    # Reorder columns to match GTF format
    gtf_columns = [
        "name",
        "source",
        "feature",
        "start",
        "end",
        "score",
        "strand",
        "frame",
        "attribute",
    ]

    df = df.select(gtf_columns)

    # Write to file
    with open(output_path, "w") as f:
        for row in df.iter_rows():
            f.write("\t".join(map(str, row)) + "\n")

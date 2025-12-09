import polars as pl

from Bio import SeqIO
from Bio.Seq import translate
from toolz import compose, juxt, first
from toolz.curried import map as mapc
from operator import attrgetter as at
from operator import methodcaller as mc
from operator import eq, gt
from functools import partial


#regulatory / ncRNA / tmRNA / tRNA / rRNA / gene / CDS


def genbank_to_dataframe(filename: str):

    # Read file
    genome = SeqIO.read(filename, "genbank")

    # features
    gene_qualifiers = ("locus_tag", "gene")
    cds_qualifiers = (
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
    r_rna_qualifiers = (
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
        "cds_extract",
    )
    t_rna_qualifiers = (
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
        "cds_extract",
    )
    tm_rna_qualifiers = (
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
        "cds_extract",
    )
    nc_rna_qualifiers = (
        "gene",
        "locus_tag",
        "protein_id",
        "function",
        "product",
        "translation",
        "transl_table",
        "codon_start",
        "inference",
        "ncRNA_class",      # replace note
        "cds_extract",
    )
    regulatory_nc_rna_qualifiers = (
        "gene",
        "locus_tag",
        "protein_id",
        "regulatory_class",  # replace function
        "note",             # no product for regulatory features
        "translation",
        "transl_table",
        "codon_start",
        "inference",
        "note_holder", # replace note
        "cds_extract",
    )
    location_attributes = ("start", "end", "strand")

    # annotations
    annotations_attributes = ("topology", "organism", "taxonomy")
    topology, organism, taxonomy = compose(
        juxt(map(lambda x: mc("get", x, None), annotations_attributes)),
        at("annotations"),
    )(genome)


    # ids
    id_attributes = ("id", "name", "description")
    id, name, description = juxt(map(at, id_attributes))(genome)

    # fn
    _impute_attributes = lambda x: mc("get", x, [""])

    _type_gene = compose(partial(eq, "gene"), at("type"))
    _type_cds = compose(partial(eq, "CDS"), at("type"))
    _type_r_rna = compose(partial(eq, "rRNA"), at("type"))
    _type_t_rna = compose(partial(eq, "tRNA"), at("type"))
    _type_tm_rna = compose(partial(eq, "tmRNA"), at("type"))
    _type_nc_rna = compose(partial(eq, "ncRNA"), at("type"))
    _type_regulatory_nc_rna = compose(partial(eq, "regulatory"), at("type"))

    # process cds features related information
    data_cds = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, cds_qualifiers)),
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

    df_cds = pl.DataFrame(data_cds, schema=cds_qualifiers)
    df_cds_pk = pl.DataFrame(data_cds_pk, schema=location_attributes)
    cds_extract = list(
        map(lambda x: str(x.extract(genome.seq)), filter(_type_cds, genome.features))
    )
    df_cds_extract = pl.DataFrame(cds_extract, schema=["cds_extract"])
    # df_cds_translate = pl.DataFrame(map(partial(translate, stop_symbol="", table=11), cds_extract), schema=["translation_fn"])

    cds = pl.concat(items=[df_cds, df_cds_pk, df_cds_extract], how="horizontal").rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag"}
    )

    # process gene features related information
    data_gene = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, gene_qualifiers)),
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

    df_gene = pl.DataFrame(data_gene, schema=gene_qualifiers)
    df_gene_pk = pl.DataFrame(data_gene_pk, schema=location_attributes)
    gene_extract = list(
        map(lambda x: str(x.extract(genome.seq)), filter(_type_gene, genome.features))
    )
    df_gene_translate = pl.DataFrame(
        map(partial(translate, stop_symbol="", table=11), gene_extract),
        schema=["translation_fn"],
    )
    df_gene_extract = pl.DataFrame(gene_extract, schema=["extract"])

    gene = pl.concat(
        items=[df_gene, df_gene_pk, df_gene_extract, df_gene_translate],
        how="horizontal",
    )

    # process rRNA features related information
    data_r_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, r_rna_qualifiers)),
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
    df_r_rna = pl.DataFrame(data_r_rna, schema=r_rna_qualifiers)
    df_r_rna_pk = pl.DataFrame(data_r_rna_pk, schema=location_attributes)
    r_rna = pl.concat(
        items=[df_r_rna, df_r_rna_pk],
        how="horizontal",
    ).rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag"}
    )

    # process tRNA features related information
    data_t_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, t_rna_qualifiers)),
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
    df_t_rna = pl.DataFrame(data_t_rna, schema=t_rna_qualifiers)
    df_t_rna_pk = pl.DataFrame(data_t_rna_pk, schema=location_attributes)
    t_rna = pl.concat(
        items=[df_t_rna, df_t_rna_pk],
        how="horizontal",
    ).rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag"}
    )

    # process tmRNA features related information
    data_tm_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, tm_rna_qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_tm_rna, genome.features),
        )
    )
    data_tm_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_tm_rna, genome.features),
        )
    )
    df_tm_rna = pl.DataFrame(data_tm_rna, schema=tm_rna_qualifiers)
    df_tm_rna_pk = pl.DataFrame(data_tm_rna_pk, schema=location_attributes)
    tm_rna = pl.concat(
        items=[df_tm_rna, df_tm_rna_pk],
        how="horizontal",
    ).rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag"}
    )

    # process ncRNA features related information
    data_nc_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, nc_rna_qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_nc_rna, genome.features),
        )
    )
    data_nc_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_nc_rna, genome.features),
        )
    )
    df_nc_rna = pl.DataFrame(data_nc_rna, schema=nc_rna_qualifiers)
    df_nc_rna_pk = pl.DataFrame(data_nc_rna_pk, schema=location_attributes)
    nc_rna = pl.concat(
        items=[df_nc_rna, df_nc_rna_pk],
        how="horizontal",
    ).rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag", "ncRNA_class": "note"}
    )

    # process regulatory ncRNA features related information
    data_regulatory_nc_rna = list(
        map(
            compose(
                list,
                mapc(first),
                juxt(map(_impute_attributes, regulatory_nc_rna_qualifiers)),
                at("qualifiers"),
            ),
            filter(_type_regulatory_nc_rna, genome.features),
        )
    )
    data_regulatory_nc_rna_pk = list(
        map(
            compose(
                list,
                mapc(at("real")),
                juxt(map(at, location_attributes)),
                at("location"),
            ),
            filter(_type_regulatory_nc_rna, genome.features),
        )
    )
    df_regulatory_nc_rna = pl.DataFrame(data_regulatory_nc_rna, schema=regulatory_nc_rna_qualifiers)
    df_regulatory_nc_rna_pk = pl.DataFrame(data_regulatory_nc_rna_pk, schema=location_attributes)
    regulatory_nc_rna = pl.concat(
        items=[df_regulatory_nc_rna, df_regulatory_nc_rna_pk],
        how="horizontal",
    ).rename(
        mapping={"gene": "cds_gene", "locus_tag": "cds_locus_tag", "note": "product", "regulatory_class": "function", "note_holder": "note"}
    )

    # join all the dataframes
    CDS_COLUMNS = [
        "cds_gene",
        "cds_locus_tag",
        "protein_id",
        "function",
        "product",
        "translation",
        "transl_table",
        "codon_start",
        "start",
        "end",
        "strand",
        "cds_extract",
        "inference",
        "note",
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
        items=[cds.select(*[pl.col(c) for c in CDS_COLUMNS]), r_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), t_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), tm_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), nc_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), regulatory_nc_rna.select(*[pl.col(c) for c in CDS_COLUMNS])],
        how="vertical",
    )

    sizes = gt(first(product.shape), 0), gt(first(gene.shape), 0)
    match sizes:
        case (True, True):
            df = product.join(
                other=gene, on=["start", "end", "strand"], how="full", coalesce=True
            )
        case (True, False):
            df = product.with_columns(*[pl.lit(None).alias(c) for c in GENE_COLUMNS])
        case (False, True):
            df = gene.with_columns(*[pl.lit(None).alias(c) for c in CDS_COLUMNS])

    df = df.with_columns(
        id=pl.lit(id),
        name=pl.lit(name),
        description=pl.lit(description),
        topology=pl.lit(topology),
        organism=pl.lit(organism),
        taxonomy=pl.lit(taxonomy),
        filename=pl.lit(filename),
    ).select(*[pl.col(c) for c in CDS_COLUMNS + GENE_COLUMNS + GENERIC_COLUMNS])

    return df





####### USAGE EXAMPLE ########

#file = 'temp/bakta_outputs/p9b1_lys_spbeta/p9b1_lys_spbeta.gbff'
#p9b1_df = genbank_to_dataframe(file)
#p9b1_df.write_parquet('temp/parquets/p9b1_bacterial.parquet')

# file = 'temp/bakta_outputs/168/168.gbff'
# bs168_df = genbank_to_dataframe(file)
# bs168_df.write_parquet('temp/parquets/168_bacterial.parquet')

# file = 'temp/bakta_outputs/mb8b7/mb8b7.gbff'
# mb8b7_df = genbank_to_dataframe(file)
# mb8b7_df.write_parquet('temp/parquets/mb8b7_bacterial.parquet')
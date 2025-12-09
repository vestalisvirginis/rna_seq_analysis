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
        "function",
        "note",             # no product for regulatory features
        "translation",
        "transl_table",
        "codon_start",
        "inference",
        "regulatory_class", # replace note
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
        items=[cds.select(*[pl.col(c) for c in CDS_COLUMNS]), r_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), t_rna.select(*[pl.col(c) for c in CDS_COLUMNS])],
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



df.with_columns(
    (pl.when(pl.col('gene').is_null())
            .then(pl.col('cds_gene'))
            .otherwise(pl.col('gene')))
        .alias('gene'),
    (pl.when(pl.col('locus_tag').is_null())
            .then(pl.col('cds_locus_tag'))
            .otherwise(pl.col('locus_tag')))
        .alias('locus_tag'),
        (pl.when(pl.col('strand')==-1)
            .then(pl.col('end'))
            .otherwise(pl.col('start')))
        .alias('new_start'),
        (pl.when(pl.col('strand')==-1)
            .then(pl.col('start'))
            .otherwise(pl.col('end')))
        .alias('new_end'),
)

)

with pl.Config(tbl_cols=100):






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
    #cds_extract = list(
    #    map(lambda x: str(x.extract(genome.seq)), filter(_type_cds, genome.features))
    #)
    #df_cds_extract = pl.DataFrame(cds_extract, schema=["cds_extract"])
    # df_cds_translate = pl.DataFrame(map(partial(translate, stop_symbol="", table=11), cds_extract), schema=["translation_fn"])

    cds = pl.concat(items=[df_cds, df_cds_pk], how="horizontal").with_columns(pl.lit('CDS').alias('feature'))

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
    #gene_extract = list(
    #    map(lambda x: str(x.extract(genome.seq)), filter(_type_gene, genome.features))
    #)
    #df_gene_translate = pl.DataFrame(
    #    map(partial(translate, stop_symbol="", table=11), gene_extract),
    #    schema=["translation_fn"],
    #)
    #df_gene_extract = pl.DataFrame(gene_extract, schema=["extract"])

    gene = pl.concat(
        items=[df_gene, df_gene_pk],
        how="horizontal",
    ).with_columns(pl.lit('gene').alias('feature'))

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
    r_rna = pl.concat(
        items=[df_r_rna, df_r_rna_pk],
        how="horizontal",
    ).with_columns(pl.lit('rRNA').alias('feature'))

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
    t_rna = pl.concat(
        items=[df_t_rna, df_t_rna_pk],
        how="horizontal",
    ).with_columns(pl.lit('tRNA').alias('feature'))

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
        "feature"
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
        items=[cds.select(*[pl.col(c) for c in CDS_COLUMNS]),r_rna.select(*[pl.col(c) for c in CDS_COLUMNS]), t_rna.select(*[pl.col(c) for c in CDS_COLUMNS])],
        how="vertical",
    )

    sizes = gt(first(product.shape), 0), gt(first(gene.shape), 0)
    match sizes:
        case (True, True):
            df = product.join(
                other=gene.with_columns(pl.all().name.suffix("_gene")), on=["start", "end", "strand"], how="full", coalesce=True
            )
        case (True, False):
            df = product.with_columns(*[pl.lit(None).alias(f'{c}_gene') for c in CDS_COLUMNS])
        case (False, True):
            df = gene.with_columns(pl.all().name.suffix("_gene")).with_columns(*[pl.lit(None).alias(c) for c in CDS_COLUMNS])

    df = df.with_columns(
        id=pl.lit(id),
        name=pl.lit(name),
        description=pl.lit(description),
        topology=pl.lit(topology),
        organism=pl.lit(organism),
        taxonomy=pl.lit(taxonomy),
        filename=pl.lit(filename),
    ).select(*[pl.col(c) for c in CDS_COLUMNS + [f'{c}_gene' for c in CDS_COLUMNS] + GENERIC_COLUMNS])

    return df



new_df = df.with_columns(
    (pl.when(pl.col('gene_gene').is_null())
            .then(pl.col('gene'))
            .otherwise(pl.col('gene_gene')))
        .alias('gene_gene'),
    (pl.when(pl.col('locus_tag_gene').is_null())
            .then(pl.col('locus_tag'))
            .otherwise(pl.col('locus_tag_gene')))
        .alias('locus_tag_gene'),
        (pl.when(pl.col('strand')==-1)
            .then(pl.col('end'))
            .otherwise(pl.col('start')))
        .alias('new_start'),
        (pl.when(pl.col('strand')==-1)
            .then(pl.col('start'))
            .otherwise(pl.col('end')))
        .alias('new_end'),
        (pl.when(pl.col('protein_id').is_null() & pl.col('feature')==pl.lit('CDS'))
            .then(pl.col('locus_tag'))
            .otherwise(pl.col('protein_id')))
        .alias('protein_id'),
)


with pl.Config(tbl_cols=100):

col_for_file = ['new_start', 'new_end', 'feature', 'locus_tag', 'gene', 'product', 'inference', 'note', 'codon_start', 'transl_table']


final_df = pl.concat(items=[
   new_df.select(*[pl.col(c) for c in[c for c in CDS_COLUMNS]+['new_start', 'new_end']]),
   new_df.select(*[pl.col(c) for c in[f'{c}_gene' for c in CDS_COLUMNS]+['new_start', 'new_end']]).with_columns(pl.when(pl.col('feature_gene').is_null()).then(pl.lit('gene').alias('feature_gene'))).select(~cs.ends_with('_gene'), cs.ends_with('_gene').name.map(lambda s: s.removesuffix('_gene'))).select(*[pl.col(c) for c in[c for c in CDS_COLUMNS]+['new_start', 'new_end']]),
], how='vertical').select(
    col_for_file
    ).unpivot(
        index=['new_start', 'new_end', 'feature'], 
        variable_name='key'
    ).filter(
            pl.col('value').is_not_null()
    ).filter(
            pl.col('value')!=''
    ).sort(
        'feature', 
        descending=True,
    ).sort(
        'new_start'
    )



final_df.select('new_start', 'new_end', 'feature').unique().sort('feature', descending=True).sort('new_start').with_row_index()

with pl.Config(tbl_rows=100):

pl.concat(items=[final_df.select('new_start', 'new_end', 'feature').unique().sort('feature', descending=True).sort('new_start').with_columns(pl.lit('').alias('key'), pl.lit('').alias('value')), final_df], how='vertical').sort('feature', descending=True).sort('new_start')

final_df.write_csv('ndmed_annotation', include_header=False, separator='\t', line_terminator='\n')


final_w_index = final_df.join(final_df.select('new_start', 'new_end', 'feature').unique().sort('feature', descending=True).sort('new_start').with_row_index(), on=['new_start', 'new_end', 'feature'], how='left')

COL_ORDER = ['new_start', 'new_end', 'feature', 'key', 'value', 'index']

pl.concat(items=[
    final_w_index.select('key', 'value', 'index').unique().with_columns(pl.lit(None).alias('new_start').cast(pl.Int64), pl.lit(None).alias('new_end').cast(pl.Int64), pl.lit(None).alias('feature').cast(pl.String)).select(*COL_ORDER), 
    final_w_index.select('new_start', 'new_end', 'feature', 'index').unique().with_columns(pl.lit(None).alias('key'), pl.lit(None).alias('value')).select(*COL_ORDER)], 
    how='vertical').sort('key').sort('feature', descending=True).sort('new_start', nulls_last=True).sort('index')




pl.concat(items=[
     ...:     final_w_index.select('key', 'value', 'index').unique().with_columns(pl.lit(None).alias('new_start').cast(pl.Int64), pl.lit(None).alias('new_end').cast(p
     ...: l.Int64), pl.lit(None).alias('feature').cast(pl.String)).select(*COL_ORDER),
     ...:     final_w_index.select('new_start', 'new_end', 'feature', 'index').unique().with_columns(pl.lit(None).alias('key'), pl.lit(None).alias('value')).select(*C
     ...: OL_ORDER)],
     ...:     how='vertical').sort('key').sort('feature', descending=True).sort('new_start', nulls_last=True).sort('index').drop('index').write_csv('temp/ndmed_annotation'
     ...: , include_header=False, separator='\t', line_terminator='\n')


from pathlib import Path

def write_fasta(df: pl.DataFrame, file: str):
    """
    Write a fasta file from a dataframe
    """

    # write the fasta file

    with open(file, "w") as _f:
                for data in (
                    df.filter(pl.col("filename").str.contains(Path(file).stem))
                    .select("key", "extract")
                    .iter_rows(named=True)
                ):
                    _f.write(
                        ">%s \n%s\n"
                        % (
                            data["key"],
                            data["extract"],
                        )
                    )



### On-target and Off-target


full_data = pl.concat([df, df1, df2])

full_rrna = full_data.filter(pl.col('product').str.contains('ribosomal'))

def find_rrna_hits(sg_seq: str, rrna_table: pl.DataFrame) -> list[str]:
    matches = rrna_table.filter(pl.col("extract").str.contains(sg_seq))
    return matches["cds_locus_tag"].to_list()

oligos = pl.read_parquet('temp/analysis/parquets/all_targets/part-00000-c53ae72d-21d8-4a35-8c96-e7cec2a17177-c000.snappy.parquet')

new_oligos = oligos.with_columns([
    pl.col("target").map_elements(lambda x: find_rrna_hits(x, full_rrna)).alias("rrna_hits")
])

mrna = full_data.filter(~pl.col('product').str.contains('ribosomal'))

import regex as re

def find_off_targets(sg_seq: str, gene_table: pl.DataFrame, max_mismatches: int = 3) -> list[str]:
    pattern = f"({sg_seq}){{e<={max_mismatches}}}"
    hits = []
    for row in gene_table.iter_rows(named=True):
        if re.search(pattern, row["extract"]):
            hits.append(row["cds_locus_tag"])
    return hits

# Apply to all oligos
off_targets = oligos.with_columns([
    pl.col("target").map_elements(lambda x: find_off_targets(x, mrna)).alias("off_targets")
])





# targeted sequences not in ribosomal rna

new_oligos.filter(pl.col('rrna_hits')==[]).count()


off_targets.filter(pl.col('off_targets')==[]).count() # no off target
off_targets.filter(~(pl.col('off_targets')==[])).count() #off target

off_targets.filter(~(pl.col('off_targets')==[])).select('off_targets').unique()



import itertools
off_target_lt = list(itertools.chain(*off_targets.filter(~(pl.col('off_targets')==[])).select('off_targets').unique().to_series().to_list()))


full_data.filter(pl.col('cds_locus_tag').is_in(off_target_lt)).select('cds_gene','cds_locus_tag','function', 'product')

# check no hit + no off-target
new_oligos_all.filter(pl.col('rrna_hits')==[]).select('target').join(pl.concat([off_targets_all,off_targets]).filter(pl.col('off_targets')==[]), on='target', how='semi')
#check no hit + off_target
new_oligos_all.filter(pl.col('rrna_hits')==[]).select('target').join(pl.concat([off_targets_all,off_targets]).filter(~(pl.col('off_targets')==[])), on='target', how='semi')

# hits + no off-target
new_oligos_all.filter(~(pl.col('rrna_hits')==[])).join(pl.concat([off_targets_all,off_targets]).filter(pl.col('off_targets')==[]), on='target', how='semi')
# hits + off-target
new_oligos.filter(~(pl.col('rrna_hits')==[])).join(off_targets.filter(~(pl.col('off_targets')==[])), on='target', how='semi')


off = pl.concat([off_targets_all,off_targets]).filter(~(pl.col('off_targets')==[])).join(new_oligos_all.filter(pl.col('rrna_hits')==[]), on='target', how='anti')
off_target_lt = list(itertools.chain(*off.select('off_targets').unique().to_series().to_list()))

# NC_000964.3, NZ_CP045811.1, NZ_CP045821.1
full_data.filter(pl.col('cds_locus_tag').is_in(off_target_lt)).filter(pl.col('id')=='NZ_CP045811.1').select('cds_gene','cds_locus_tag','function', 'product')
from dagster import load_assets_from_package_module

from . import loading, trimming, alignement


LOADING = "loading"
TRIMMING = "trimming"
MAPPING = "mapping"

loading_assets = load_assets_from_package_module(loading, group_name=LOADING)
trimming_assets = load_assets_from_package_module(trimming, group_name=TRIMMING)
mapping_assets = load_assets_from_package_module(alignement, group_name=MAPPING)


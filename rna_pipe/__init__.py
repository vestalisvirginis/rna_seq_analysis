from dagster import Definitions, PipesSubprocessClient, load_assets_from_package_module

from .assets import (
    loading_assets,
    mapping_assets,
    quantification_assets,
    trimming_assets,
)

all_assets = [
    *loading_assets,
    *trimming_assets,
    *mapping_assets,
    *quantification_assets,
]


defs = Definitions(
    assets=all_assets, resources={"pipes_subprocess_client": PipesSubprocessClient()}
)

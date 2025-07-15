from dagster import Definitions, load_assets_from_package_module, PipesSubprocessClient

from .assets import loading_assets, trimming_assets, mapping_assets


all_assets = [*loading_assets, *trimming_assets, *mapping_assets]


defs = Definitions(
    assets=all_assets,
    resources={"pipes_subprocess_client": PipesSubprocessClient()}
)
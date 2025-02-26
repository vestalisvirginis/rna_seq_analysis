import shutil

from dagster import AssetExecutionContext, Definitions, PipesSubprocessClient, asset, file_relative_path


@asset
def cli_command_asset(
    context: AssetExecutionContext, pipes_subprocess_client: PipesSubprocessClient
):
    cmd = [shutil.which("bash"),  file_relative_path(__file__, "shell_test.sh")]
    return pipes_subprocess_client.run(
        command=cmd,
        context=context,
        #env={"MY_ENV_VAR": "example_value"},
    ).get_materialize_result()


defs = Definitions(
    assets=[cli_command_asset],
    resources={"pipes_subprocess_client": PipesSubprocessClient()},
)
from dagster import asset

@asset()
def mapping():
    return "This is a mapping asset."
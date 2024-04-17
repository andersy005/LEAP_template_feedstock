"""
A synthetic prototype recipe
"""

import zarr
import os
from dataclasses import dataclass
from typing import List, Dict, Any
import apache_beam as beam
from datetime import datetime, timezone
from leap_data_management_utils.data_management_transforms import Copy, InjectAttrs
from pangeo_forge_recipes.patterns import pattern_from_file_sequence
from pangeo_forge_recipes.transforms import (
    OpenURLWithFSSpec,
    OpenWithXarray,
    StoreToZarr,
    ConsolidateMetadata,
    ConsolidateDimensionCoordinates,
)
from ruamel.yaml import YAML

yaml = YAML(typ="safe")

def find_recipe_meta(catalog_meta: List[Dict[str, str]], r_id: str) -> Dict[str, str]:
    # Iterate over each dictionary in the list
    for d in catalog_meta:
        # Check if the 'id' key matches the search_id
        if d["id"] == r_id:
            return d
    print(
        f"Could not find {r_id=}. Got the following recipe_ids: {[d['id'] for d in catalog_meta]}"
    )
    return None  # Return None if no matching dictionary is found


# load the global config values (we will have to decide where these ultimately live)
catalog_meta = yaml.load(open("feedstock/catalog.yaml"))

if os.getenv("GITHUB_ACTIONS") == "true":
    print("Running inside GitHub Actions.")

    # Get final store path from catalog.yaml input
    target_small = find_recipe_meta(catalog_meta["stores"], "small")["url"]
    target_large = find_recipe_meta(catalog_meta["stores"], "large")["url"]
    pgf_build_attrs = get_pangeo_forge_build_attrs()
else:
    print("Running locally. Deactivating final copy stage.")
    # this deactivates the final copy stage for local testing execution
    target_small = False
    target_large = False
    pgf_build_attrs = {}

print("Final output locations")
print(f"{target_small=}")
print(f"{target_large=}")
print(f"{pgf_build_attrs=}")

## Monthly version
input_urls_a = [
    "gs://cmip6/pgf-debugging/hanging_bug/file_a.nc",
    "gs://cmip6/pgf-debugging/hanging_bug/file_b.nc",
]
input_urls_b = [
    "gs://cmip6/pgf-debugging/hanging_bug/file_a_huge.nc",
    "gs://cmip6/pgf-debugging/hanging_bug/file_b_huge.nc",
]

pattern_a = pattern_from_file_sequence(input_urls_a, concat_dim="time")
pattern_b = pattern_from_file_sequence(input_urls_b, concat_dim="time")


# small recipe
small = (
    beam.Create(pattern_a.items())
    | OpenURLWithFSSpec()
    | OpenWithXarray()
    | StoreToZarr(
        store_name="small.zarr",
        # FIXME: This is brittle. it needs to be named exactly like in meta.yaml...
        # Can we inject this in the same way as the root?
        # Maybe its better to find another way and avoid injections entirely...
        combine_dims=pattern_a.combine_dim_keys,
    )
    | InjectAttrs(pgf_build_attrs)
    | ConsolidateDimensionCoordinates()
    | ConsolidateMetadata()
    | Copy(target=target_small)
)

# larger recipe
large = (
    beam.Create(pattern_b.items())
    | OpenURLWithFSSpec()
    | OpenWithXarray()
    | StoreToZarr(
        store_name="large.zarr",
        combine_dims=pattern_b.combine_dim_keys,
    )
    | InjectAttrs(pgf_build_attrs)
    | ConsolidateDimensionCoordinates()
    | ConsolidateMetadata()
    | Copy(target=target_large)
)

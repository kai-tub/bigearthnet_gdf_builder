# Quickstart
The primary use-case for this library is to be used as CLI-tool to generate
the desired parquet-files described in the {ref}`introduction <intro>` page.

To use the CLI-tool, install the library via pip/conda/pipx:
```
pip install bigearthnet_gdf_builder
```

The most relevant functions are exposed as CLI entry points.

To build the tabular data, use:
- `ben_gdf_builder --help` or
- `python -m bigearthnet_gdf_builder.builder --help`

There are four command types:
1. `build-raw-ben-s1/2-parquet` (depending on BEN-S1/S2 source data)
    - Convert all JSON files to a common GeoDataFrame parquet file
1. `extend-ben-s1/2-parquet` (depending on the source of the GeoDataFrame)
    - Add commonly-used metadata to the BEN-S1/2 parquet file
1. `remove-discouraged-parquet-entries` (works for both BEN-S1/S2 GeoDataFrame's)
    - Remove rows from a BEN-S1/S2 parquet file that are not recommended for deep-learning
1. `build-recommended-s1/2-parquet` (depending on BEN-S1/S2 source data)
    - Combines all of the above to produce a BEN-S1/2 parquet file only with the recommended patches extended with commonly-used metadata

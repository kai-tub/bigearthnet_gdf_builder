# BigEarthNet GeoDataFrame Builder
> A package to generate and extend BigEarthNet GeoDataFrame's.


This library provides a collection of functions to generate and extend GeoDataFrames for the [BigEarthNet](bigearth.net) dataset.

`bigearthnet_gdf_builder` tries to accomplish two goals:

1. Easily generate [geopandas](https://geopandas.org/en/stable/) [GeoDataFrame](https://geopandas.org/en/stable/getting_started/introduction.html) by passing a BigEarthNet archive directory.
   - Allow for easy top-level statistical analysis of the data in a familiar _pandas_-style
   - Provide functions to enrich GeoDataFrames with often required BigEarthNet metadata (like the season or country of the patch)
2. Simplify the building procedure by providing a command-line interface with reproducible results

## Installation
<!-- I strongly recommend to use [mamba](https://github.com/mamba-org/mamba) or `conda` with [miniforge](https://github.com/conda-forge/miniforge) to install the package with:
- `mamba/conda install bigearthnet-common -c conda-forge`

As the `bigearthnet_common` tool is built on top of `geopandas` the same restrictions apply.
For more details please review the [geopandas installation documentation](https://geopandas.org/en/stable/getting_started/install.html).

The package is also available via PyPI and could be installed with:
- `pip install bigearthnet_common` (not recommended) -->

## TL;DR
The most relevant functions are exposed as CLI entry points.

To build the tabular data, use:
- `ben_gdf_builder --help` or
- `python -m bigearthnet_gdf_builder.builder --help`


## Deep Learning

One of the primary purposes of the dataset is to allow deep learning researchers and practitioners to train their models on multi-spectral satellite data.
In that regard, there is a general recommendation to drop patches that are covered by seasonal snow or clouds.
Also, the novel 19-class nomenclature should be preferred over the original 43-class nomenclature.
As a result of these recommendations, some patches have to be _excluded_ from the original raw BigEarthNet dataset that is provided at [BigEarthNet](bigearth.net).

To simplify the procedure of pre-converting the JSON metadata files, the library provides a single command that will generate a recommended GeoDataFrame with extra metadata (country/season data of each patch) while dropping all patches that are not recommended for deep learning research.
Functions for both archives, BEN-S1 and BEN-S2, are provided.

To generate such a GeoDataFrame and store it as an `parquet` file, use:

- `ben_gdf_builder build-recommended-s2-parquet` (available after installing package) or
- `python -m bigearthnet_gdf_builder.builder build-recommended-s2-parquet`
- `ben_gdf_builder build-recommended-s1-parquet` (available after installing package) or
- `python -m bigearthnet_gdf_builder.builder build-recommended-s1-parquet`

If you want to read the raw JSON files and convert those to a GeoDataFrame file without dropping any patches or adding any metadata, use:

- `ben_gdf_builder build-raw-ben-s2-parquet` (available after installing package) or
- `python -m bigearthnet_gdf_builder.builder build-raw-ben-s2-parquet`
- `ben_gdf_builder build-raw-ben-s1-parquet` (available after installing package) or
- `python -m bigearthnet_gdf_builder.builder build-raw-ben-s1-parquet`

## Relation to bigearthnet_common

There exists a _logical, circular_ dependency between [bigearthnet_common](https://github.com/kai-tub/bigearthnet_common) and this project.
`bigearthnet_gdf_builder` uses functions from `bigearthnet_common` to safely read the BigEarthNet JSON metadata files from the Sentine-1/2 archives.

The resulting `raw` GeoDataFrame is further processed to the `extended` representation with extra metadata (season of the acquisition date, country, 19-class nomenclature, etc.).

To easily provide a dependency free interaction with BigEarthnet, mainly to quickly create subsets, some of these results are distributed _in_ the `bigearthnet_common` package.
For example, this allows a user to quickly retrieve the corresponding S2 patch of an S1 input patch without needing to access the JSON file or the result of the `bigearthnet_gdf_builder`.

The correctness of some `bigearthnet_common` functions depend on the correctness of this project!
As such, `bigearthnet_gdf_builder` should never use functions from `bigearthnet_common` that make use of the distributed data.

## Contributing

Contributions are always welcome!

Please look at the corresponding `ipynb` notebook from the `nbs` folder to review the source code.
These notebooks include extensive documentation, visualizations, and tests.
The automatically generated Python files are available in the `bigearthnet_gdf_builder` module.

More information is available in the [contributing guidelines](https://github.com/kai-tub/bigearthnet_common/blob/main/.github/CONTRIBUTING.md) document.

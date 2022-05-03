# Relation to other tools

There exists a _logical, circular_ dependency between [bigearthnet_common](https://github.com/kai-tub/bigearthnet_common) and this project.
`bigearthnet_gdf_builder` uses functions from `bigearthnet_common` to safely read the BigEarthNet JSON metadata files from the Sentine-1/2 archives.

The resulting `raw` GeoDataFrame is further processed to the `extended` representation with extra metadata (season of the acquisition date, country, 19-class nomenclature, etc.).

To easily provide a dependency free interaction with BigEarthnet, mainly to quickly create subsets, some of these results are distributed _in_ the `bigearthnet_common` package.
For example, this allows a user to quickly retrieve the corresponding S2 patch of an S1 input patch without needing to access the JSON file or the result of the `bigearthnet_gdf_builder`.

The correctness of some `bigearthnet_common` functions depend on the correctness of this project!
As such, `bigearthnet_gdf_builder` should never use functions from `bigearthnet_common` that make use of the distributed data.

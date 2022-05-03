(intro)=
# BigEarthNet GDF Builder
> A package to generate and extend BigEarthNet GeoDataFrame's.

This library provides a collection of functions to generate and extend GeoDataFrames for the [BigEarthNet](https://bigearth.net) dataset.

`bigearthnet_gdf_builder` tries to accomplish two goals:

1. Easily generate [geopandas](https://geopandas.org/en/stable/) [GeoDataFrame](https://geopandas.org/en/stable/getting_started/introduction.html)'s by passing a BigEarthNet archive directory.
   - Allow for easy top-level statistical analysis of the data in a familiar _pandas_-style
   - Provide functions to enrich GeoDataFrames with often required BigEarthNet metadata (like the season or country of the patch)
2. Simplify the building procedure by providing a command-line interface with reproducible results

One of the primary purposes of the dataset is to allow deep learning researchers and practitioners to train their models on the _recommended_ BigEarthNet satellite data.
In that regard, there is a general recommendation to drop patches that are covered by seasonal snow or clouds/shadows.
Also, the novel 19-class nomenclature should be preferred over the original 43-class nomenclature.
As a result of these recommendations, some patches have to be _excluded_ from the original raw BigEarthNet dataset that is provided at [BigEarthNet](https://bigearth.net).

To simplify the procedure of pre-converting the JSON metadata files, the library provides a single command that will generate a recommended GeoDataFrame with extra metadata (country/season data of each patch) while dropping all patches that are not recommended for deep learning research.
Functions for both archives, BEN-S1 and BEN-S2, are provided.

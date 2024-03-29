import enum
import shutil
import tempfile
import warnings
from numbers import Real
from pathlib import Path
from typing import Callable, List, Tuple, Union

import requests

warnings.filterwarnings("ignore", category=UserWarning)


import appdirs
import fastcore.all as fc
import geopandas
import pandas as pd
import rich
import typer
from bigearthnet_common.base import (
    get_original_split_from_patch_name,
    get_s1_patch_directories,
    get_s2_patch_directories,
    is_cloudy_shadowy_patch,
    is_snowy_patch,
    old2new_labels,
    parse_datetime,
    read_S1_json,
    read_S2_json,
)
from bigearthnet_common.constants import COUNTRIES, COUNTRIES_ISO_A2
from fastcore.basics import compose
from pydantic import DirectoryPath, FilePath, PositiveInt, conint, validate_arguments
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from shapely.geometry import LineString, Point, Polygon, box

rich.traceback.install(show_locals=True)

COUNTRIES_URL = "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_admin_0_countries.zip"


USER_DIR = Path(appdirs.user_data_dir("bigearthnet_gdf_builder"))
USER_DIR.mkdir(exist_ok=True, parents=True)


def _get_box_from_two_coords(p1: Tuple[Real, Real], p2: Tuple[Real, Real]) -> Polygon:
    """
    Get the polygon that bounds the two coordinates.
    These values should be supplied as numerical values.
    """
    get_bounds = lambda geom: geom.bounds
    box_from_bounds = lambda bounds: box(*bounds)
    return compose(LineString, get_bounds, box_from_bounds)([p1, p2])


def box_from_ul_lr_coords(ulx: Real, uly: Real, lrx: Real, lry: Real) -> Polygon:
    """
    Build a box (`Polygon`) from upper left x/y and lower right x/y coordinates.

    This specification is the default BigEarthNet style.
    """
    return _get_box_from_two_coords([ulx, uly], [lrx, lry])


@validate_arguments
def ben_s2_patch_to_gdf(
    patch_path: Union[FilePath, DirectoryPath]
) -> geopandas.GeoDataFrame:
    """
    Given the filepath to a BigEarthNet json `_metadata_labels` file, or
    to the containing patch folder, the function will return a single row GeoDataFrame.

    The filepath is necessary, as only the filename contains the patch name.

    The datetime will be parsed with best effort and guaranteed to be in the format
    'YYYY-MM-DD hh-mm-ss' (different to BEN-S1!)

    The coordinates that indicate the upper-left-x/y and lower-right-x/y will be converted
    into a `shapely.Polygon`.

    The coordinate reference system (CRS) will be equivalent to the one given in the json file.
    Or with other words, the data is not reprojected!
    """
    json_path = (
        patch_path
        if patch_path.is_file()
        else patch_path / f"{patch_path.name}_labels_metadata.json"
    )

    data = read_S2_json(json_path)
    data["name"] = json_path.stem.rstrip("_labels_metadata")
    data["acquisition_date"] = parse_datetime(data["acquisition_date"]).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    data["geometry"] = box_from_ul_lr_coords(**data.pop("coordinates"))
    data["labels"] = [data["labels"]]
    crs = data.pop("projection")
    return geopandas.GeoDataFrame(data, crs=crs)


@validate_arguments
def ben_s1_patch_to_gdf(
    patch_path: Union[FilePath, DirectoryPath]
) -> geopandas.GeoDataFrame:
    """
    Given the filepath to a BigEarthNet json `_metadata_labels` file, or
    to the containing patch folder, the function will return a single row GeoDataFrame.

    The filepath is necessary, as only the filename contains the patch name.

    The datetime will be parsed with best effort and guaranteed to be in the format
    'YYYY-MM-DDThh-mm-ss' (different to Ben-S2!)

    The coordinates that indicate the upper-left-x/y and lower-right-x/y will be converted
    into a `shapely.Polygon`.

    The coordinate reference system (CRS) will be equivalent to the one given in the json file.
    Or with other words, the data is not reprojected!
    """
    json_path = (
        patch_path
        if patch_path.is_file()
        else patch_path / f"{patch_path.name}_labels_metadata.json"
    )

    data = read_S1_json(json_path)
    data["name"] = json_path.stem.rstrip("_labels_metadata")
    data["acquisition_time"] = parse_datetime(data["acquisition_time"]).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    data["geometry"] = box_from_ul_lr_coords(**data.pop("coordinates"))
    data["labels"] = [data["labels"]]
    crs = data.pop("projection")
    return geopandas.GeoDataFrame(data, crs=crs)


def ben_s2_patch_to_reprojected_gdf(
    patch_path: Union[FilePath, DirectoryPath], target_proj: str = "epsg:3035"
) -> geopandas.GeoDataFrame:
    """
    Calls `ben_s2_patch_to_gdf` and simply reprojects the resulting GeoDataFrame afterwards to the
    given `target_proj`.

    This is a tiny wrapper to ensure that the generated BEN GeoDataFrame's can be concatenated and have a
    common coordinate reference system.

    See `ben_s2_patch_to_gdf` for more details.
    """
    return ben_s2_patch_to_gdf(patch_path).to_crs(target_proj)


def ben_s1_patch_to_reprojected_gdf(
    patch_path: Union[FilePath, DirectoryPath], target_proj: str = "epsg:3035"
) -> geopandas.GeoDataFrame:
    """
    Calls `ben_s1_patch_to_gdf` and simply reprojects the resulting GeoDataFrame afterwards to the
    given `target_proj`.

    This is a tiny wrapper to ensure that the generated BEN GeoDataFrame's can be concatenated and have a
    common coordinate reference system.

    See `ben_s1_patch_to_gdf` for more details.
    """
    return ben_s1_patch_to_gdf(patch_path).to_crs(target_proj)


@validate_arguments
def _parallel_gdf_path_builder(
    paths: List[Path],
    gdf_builder: Callable[[Path, str], geopandas.GeoDataFrame],
    n_workers: PositiveInt = 8,
    progress: bool = True,
    target_proj: str = "epsg:3035",
) -> geopandas.GeoDataFrame:
    """
    Build a single `geopandas.GeoDataFrame` by applying the
    `gdf_builder` function in parallel with `n_worker` processes.
    The `gdf_builder` function must take a path with a `target_proj`
    and return a GeoDataFrame in that `target_proj` CRS!
    By default a `progress` bar is shown.
    Note that each individual gdf must already be reprojected to a
    common CRS!

    If an empty dataframe is produced, an `ValueError` is raised.
    """
    # TODO: Check if categorical variables can greatly reduce the size
    # if this is the case, check if the unpacking performs as expected for the encoder

    # TODO understand how to set target_proj a positional variable
    gdfs = fc.parallel(
        gdf_builder,
        paths,
        progress=progress,
        n_workers=n_workers,
        target_proj=target_proj,
    )
    if len(gdfs) == 0:
        raise ValueError("Empty gdf produced! Possible wrong folder?", paths)
    gdf = pd.concat(gdfs, axis=0, ignore_index=True)
    return gdf


@fc.delegates(_parallel_gdf_path_builder)
def build_gdf_from_s2_patch_paths(
    paths: List[Path],
    **kwargs,
) -> geopandas.GeoDataFrame:
    """
    Build a single `geopandas.GeoDataFrame` from the BEN-S2 json files.
    The code will run in parallel and use `n_workers` processes.
    By default a progress-bar will be shown.

    From personal experience, the ideal number of workers is 8 in most cases.
    For laptops with fewer cores, 2 or 4 `n_workers` should be set.
    More than 8 usually leads to only minor improvements and with n_workers > 12
    the performance usually degrades.

    The function returns a single GDF with all patches reprojected to `target_proj`,
    which is `epsg:3035` by default.

    If the directory contains no S2 patch-folders, an `ValueError` is raised.
    """
    return _parallel_gdf_path_builder(paths, ben_s2_patch_to_reprojected_gdf, **kwargs)


@fc.delegates(_parallel_gdf_path_builder)
def build_gdf_from_s1_patch_paths(
    paths: List[Path],
    **kwargs,
) -> geopandas.GeoDataFrame:
    """
    Build a single `geopandas.GeoDataFrame` from the BEN-S1 json files.
    The code will run in parallel and use `n_workers` processes.
    By default a progress-bar will be shown.

    From personal experience, the ideal number of workers is 8 in most cases.
    For laptops with fewer cores, 2 or 4 `n_workers` should be set.
    More than 8 usually leads to only minor improvements and with n_workers > 12
    the performance usually degrades.

    The function returns a single GDF with all patches reprojected to `target_proj`,
    which is `epsg:3035` by default.

    If the directory contains no S2 patch-folders, an `ValueError` is raised.
    """
    return _parallel_gdf_path_builder(paths, ben_s1_patch_to_reprojected_gdf, **kwargs)


@fc.delegates(build_gdf_from_s2_patch_paths)
def get_gdf_from_s2_patch_dir(
    dir_path: DirectoryPath, **kwargs
) -> geopandas.GeoDataFrame:
    """
    Searches through `dir_path` to assemble a BEN-S2-style `GeoDataFrame`.
    Will only consider correctly named directories.
    Wraps around `get_s2_patch_directory` and `build_gdf_from_s2_patch_paths`.

    Raises an error if an empty GeoDataFrame would be produced.
    """
    patch_paths = get_s2_patch_directories(dir_path)
    gdf = build_gdf_from_s2_patch_paths(patch_paths, **kwargs)
    if len(gdf) == 0:
        raise ValueError("Empty gdf produced! Check provided directory!")
    return gdf


@fc.delegates(build_gdf_from_s1_patch_paths)
def get_gdf_from_s1_patch_dir(
    dir_path: DirectoryPath, **kwargs
) -> geopandas.GeoDataFrame:
    """
    Searches through `dir_path` to assemble a BEN-S1-style `GeoDataFrame`.
    Will only consider correctly named directories.
    Wraps around `get_s1_patch_directory` and `build_gdf_from_s1_patch_paths`.

    Raises an error if an empty GeoDataFrame would be produced.
    """
    patch_paths = get_s1_patch_directories(dir_path)
    gdf = build_gdf_from_s1_patch_paths(patch_paths, **kwargs)
    if len(gdf) == 0:
        raise ValueError("Empty gdf produced! Check provided directory!")
    return gdf


# @functools.lru_cache()
def _get_country_borders() -> geopandas.GeoDataFrame:
    "Get all country borders"
    # directly filter out irrelevant lines
    rel_cols = [
        "ISO_A3",
        "ISO_A2",
        "NAME",
        "geometry",
    ]

    # Now requires to provide some valid user-agent header
    # gdf = geopandas.read_file(COUNTRIES_URL)
    with tempfile.TemporaryFile() as fp:
        resp = requests.get(
            COUNTRIES_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                "Error downloading reference shapefile. Probably due to some server issues."
            )
        fp.write(resp.content)
        fp.seek(0)
        gdf = geopandas.read_file(fp)

    # NOTE: Update to the admin naturalearthdataset has removed the
    # ISO_A2 label for Kosovo, to remain compatible with previous version,
    # the function will inject the disputed ISO_A2 code for Kosovo
    kosovo_index = gdf[gdf["NAME"] == "Kosovo"].index
    gdf.loc[kosovo_index, "ISO_A2"] = "XK"

    return gdf[rel_cols]


def get_ben_countries_gdf() -> geopandas.GeoDataFrame:
    """
    Return a `GeoDataFrame` that includes the shapes of each
    country from the BigEarthNet dataset.

    This is a subset of the naturalearthdata 10m-admin-0-countries dataset:

    https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries
    """
    borders = _get_country_borders()
    ben_borders = borders[borders["ISO_A2"].isin(COUNTRIES_ISO_A2)].copy()
    return ben_borders


def assign_to_ben_country(
    gdf: geopandas.GeoDataFrame, crs: str = "epsg:3035"
) -> geopandas.GeoDataFrame:
    """
    Takes a GeoDataFrame as an input and appends a `country` column.
    The `country` column indicates the closest BEN country.

    The function calculates the centroid of each input geometry with the `crs` projection.
    These centroids are then used to find and assign the entry to the closest BEN country.
    Centroids help to more deterministically assign a border-crossing patch to a country.
    For the small BEN patches (1200mx1200m) the _error_ of the approximation is negligible
    and a good heuristic to assign the patch to the country with the largest overlap.
    """
    with Progress(
        TextColumn("{task.description}"),
        SpinnerColumn("bouncingBall"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Reprojecting", total=1)
        local_gdf = gdf.to_crs(crs)
        progress.update(task, completed=1)

        # has column called NAME for country name
        task = progress.add_task("Loading country shapes", total=1)
        borders = get_ben_countries_gdf()
        borders = borders.to_crs(crs)
        progress.update(task, completed=1)

        task = progress.add_task("Calculating centroids", total=1)
        local_gdf.geometry = local_gdf.geometry.centroid
        progress.update(task, completed=1)

        task = progress.add_task("Assigning data to countries", total=1)
        nn_gdf = local_gdf.sjoin_nearest(borders, how="inner")
        progress.update(task, completed=1)

        gdf["country"] = nn_gdf["NAME"]
    return gdf


class Season(str, enum.Enum):
    """
    A simple season class.
    """

    Winter = "Winter"
    Spring = "Spring"
    Summer = "Summer"
    Fall = "Fall"

    @classmethod
    def from_idx(cls, idx):
        return list(cls)[idx]

    def __str__(self):
        return self.value


@validate_arguments
def _month_to_season(month: conint(ge=1, le=12)) -> Season:
    return Season.from_idx(month % 12 // 3)


def tfm_month_to_season(dates: pd.Series) -> pd.Series:
    """
    Uses simple mathmatical formula to transform date
    to seasons string given their months.

    The season is calculated as the meterological season, assuming
    that we are on the northern hemisphere.
    """
    return pd.to_datetime(dates).dt.month.apply(_month_to_season)


@validate_arguments
def filter_season(df, date_col: str, season: Season) -> pd.DataFrame:
    seasons = tfm_month_to_season(df[date_col])
    return df[seasons == season]


def _add_full_ben_metadata(
    gdf: geopandas.GeoDataFrame, s2_name_col: str, date_col: str
) -> geopandas.GeoDataFrame:
    """
    A function that adds all the entire BigEarthNet metadata.
    To be able to be used with S1 and S2 sources, the provided
    gdf needs to also get a series of `s2_names` to use the same
    logic for S1 that is used for S2 sources.
    Similarly, the `date_col` must be given.
    """
    gdf["new_labels"] = gdf["labels"].apply(old2new_labels)
    gdf["snow"] = gdf[s2_name_col].apply(is_snowy_patch)
    gdf["cloud_or_shadow"] = gdf[s2_name_col].apply(is_cloudy_shadowy_patch)
    gdf["original_split"] = gdf[s2_name_col].apply(get_original_split_from_patch_name)
    gdf = assign_to_ben_country(gdf)
    gdf["season"] = tfm_month_to_season(gdf[date_col])
    return gdf


# Split into two functions, as the source _guessing_ logic
# may lead to confusing/unhelpful error messages
# and by splitting the function, future updates
# to the archives should be easier to incorporate.
# There may be a future in which these two functions could be combined.
def add_full_ben_s1_metadata(gdf: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:
    """
    This is a wrapper around many functions from this library.
    It requires an input `GeoDataFrame` in *S1-BigEarthNet* style.

    See `get_gdf_from_s1_patch_dir` for details to create a new `GeoDataFrame`.
    This function adds the following columns:

    - `snow`: `bool` - Whether or not the patch contains seasonal snow
    - `cloud_or_shadow`: `bool` - Whether or not the patch contains clouds/shadows
    - `original_split`: One of: `train|validation|test|None`; Indicates to which
        split the patch was originally assigned to
    - `new_labels`: `label|None` - The 19-label nomenclature or None if
        no target labels exist.
    - `country`: `str` - The name of the BigEarthNet country the patch belongs to.
    - `season`: `str` - The season in which the tile was aquired.

    In short, the function will add all the available metadata.
    """
    required_col_names = {
        "acquisition_time",
        "name",
        "labels",
        "corresponding_s2_patch",
    }
    diff = required_col_names - set(gdf.columns)
    if len(diff) != 0:
        # note that possibly wrong date-column is shown in error message
        raise ValueError("The provided gdf is missing required columns: ", diff)
    return _add_full_ben_metadata(gdf, "corresponding_s2_patch", "acquisition_time")


def add_full_ben_s2_metadata(gdf: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:
    """
    This is a wrapper around many functions from this library.
    It requires an input `GeoDataFrame` in *S2-BigEarthNet* style.

    See `get_gdf_from_s2_patch_dir` for details to create a new `GeoDataFrame`.
    This function adds the following columns:

    - `snow`: `bool` - Whether or not the patch contains seasonal snow
    - `cloud_or_shadow`: `bool` - Whether or not the patch contains clouds/shadows
    - `original_split`: One of: `train|validation|test|None`; Indicates to which
        split the patch was originally assigned to
    - `new_labels`: `label|None` - The 19-label nomenclature or None if
        no target labels exist.
    - `country`: `str` - The name of the BigEarthNet country the patch belongs to.
    - `season`: `str` - The season in which the tile was aquired.

    In short, the function will add all the available metadata.
    """
    # allow both datetime formats!
    required_col_names = {"acquisition_date", "name", "labels"}
    diff = required_col_names - set(gdf.columns)
    if len(diff) != 0:
        # note that possibly wrong date-column is shown in error message
        raise ValueError("The provided gdf is missing required columns: ", diff)
    return _add_full_ben_metadata(gdf, "name", "acquisition_date")


def _remove_snow_cloud_patches(gdf, s2_name_col):
    snowy = gdf[s2_name_col].apply(is_snowy_patch)
    cloudy = gdf[s2_name_col].apply(is_cloudy_shadowy_patch)
    return gdf[~(snowy | cloudy)]


def remove_bad_ben_gdf_entries(gdf: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:
    """
    It will ensure that the returned frame will only contain patches that
    also have labels for the 19 label version.

    If the GeoDataFrame doesn't include a column named `new_labels`, it
    will be created by converting the `labels` column.
    The patches that do not contain any `new_labels` are dropped.

    There are 57 patches that would have no target labels.
    Also patches that are covered by seasonal snow or clouds/shadows
    are removed if present.

    The dataframe will be reindexed.

    Note: This function applies to both S1 and S2 BigEarthNet dataframes!
    """
    s2_name_col = (
        "corresponding_s2_patch" if "corresponding_s2_patch" in gdf.columns else "name"
    )
    gdf["new_labels"] = gdf["labels"].apply(old2new_labels)
    errs = gdf["new_labels"].isna()
    gdf.drop(gdf[errs].index, inplace=True)  # remove wrong elements
    gdf = _remove_snow_cloud_patches(gdf, s2_name_col)
    gdf = gdf.reset_index(drop=True)
    return gdf


def build_raw_ben_s2_parquet(
    ben_path: Path,
    output_path: Path = Path() / "raw_ben_s2_gdf.parquet",
    n_workers: int = 8,
    target_proj: str = "epsg:3035",
    verbose: bool = True,
) -> Path:
    """
    Create a fresh BigEarthNet-S2-style parquet file
    from all the image patches in the root `ben_path` folder.
    The output will be written to `output_path`.

    The default output is `raw_ben_s2_gdf` in the current directory.

    The other options are only for advanced use.
    Returns the resolved output path.
    """
    output_path = output_path.resolve()
    gdf = get_gdf_from_s2_patch_dir(
        ben_path, n_workers=n_workers, target_proj=target_proj
    )
    gdf.to_parquet(output_path)
    if verbose:
        rich.print(f"[green]Output written to:\n {output_path}[/green]")
    return output_path


def build_raw_ben_s1_parquet(
    ben_path: Path,
    output_path: Path = Path() / "raw_ben_s1_gdf.parquet",
    n_workers: int = 8,
    target_proj: str = "epsg:3035",
    verbose: bool = True,
) -> Path:
    """
    Create a fresh BigEarthNet-S1-style parquet file
    from all the image patches in the root `ben_path` folder.
    The output will be written to `output_path`.

    The default output is `raw_ben_s1_gdf` in the current directory.

    The other options are only for advanced use.
    Returns the resolved output path.
    """
    output_path = output_path.resolve()
    gdf = get_gdf_from_s1_patch_dir(
        ben_path, n_workers=n_workers, target_proj=target_proj
    )
    gdf.to_parquet(output_path)
    if verbose:
        rich.print(f"[green]Output written to:\n {output_path}[/green]")
    return output_path


def extend_ben_s2_parquet(
    ben_parquet_path: Path,
    output_name: str = "extended_ben_s2_gdf.parquet",
    verbose: bool = True,
) -> Path:
    """
    Extend an existing BigEarthNet-S2-style parquet file.

    The output will be written next to `ben_parquet_path` with the file
    `output_name`.
    The default name is `extended_ben_s2_gdf`.

    This function heavily relies on the structure of the parquet file.
    It should only be used on parquet files that were build with this library!
    Use the functions of this package directly to have more control!
    """
    path = ben_parquet_path.resolve(strict=True)
    gdf = geopandas.read_parquet(path)
    extended_gdf = add_full_ben_s2_metadata(gdf)
    output_path = path.with_name(output_name)
    extended_gdf.to_parquet(output_path)
    if verbose:
        rich.print(f"[green]Output written to:\n {output_path}[/green]")
    return output_path


def extend_ben_s1_parquet(
    ben_parquet_path: Path,
    output_name: str = "extended_ben_s1_gdf.parquet",
    verbose: bool = True,
) -> Path:
    """
    Extend an existing BigEarthNet-S1-style parquet file.

    The output will be written next to `ben_parquet_path` with the file
    `output_name`.
    The default name is `extended_ben_s1_gdf`.

    This function heavily relies on the structure of the parquet file.
    It should only be used on parquet files that were build with this library!
    Use the functions of this package directly to have more control!
    """
    path = ben_parquet_path.resolve(strict=True)
    gdf = geopandas.read_parquet(path)
    extended_gdf = add_full_ben_s1_metadata(gdf)
    output_path = path.with_name(output_name)
    extended_gdf.to_parquet(output_path)
    if verbose:
        rich.print(f"[green]Output written to:\n {output_path}[/green]")
    return output_path


def remove_discouraged_parquet_entries(
    ben_parquet_path: Path,
    output_name: str = "cleaned_ben_gdf.parquet",
    verbose: bool = True,
) -> Path:
    """
    Remove entries of an existing BigEarthNet-style (S1 or S2) parquet file.

    The output will be written next to `ben_parquet_path` with the file
    `output_name`.
    The default name is `cleaned_ben_gdf.parquet`.

    This function only requires the input parquet file to have the
    `name` column and the original 43-class nomenclature called `labels`.
    """
    path = ben_parquet_path.resolve(strict=True)
    gdf = geopandas.read_parquet(path)
    cleaned_gdf = remove_bad_ben_gdf_entries(gdf)
    output_path = path.with_name(output_name)
    cleaned_gdf.to_parquet(output_path)
    if verbose:
        rich.print(f"[green]Output written to:\n {output_path}[/green]")
    return output_path


@fc.delegates(build_raw_ben_s2_parquet, but=["output_path"])
def build_recommended_s2_parquet(
    ben_path: Path,
    add_metadata: bool = True,
    output_path: Path = "final_ben_s2.parquet",
    **kwargs,
) -> Path:
    """
    Generate the recommended S2-GeoDataFrame and save
    it as a parquet file.

    It will call `build_raw_ben_s2_parquet` under the hood and remove
    patches that are not recommended for DL.
    If `add_metadata` is set, the GeoDataFrame will be
    enriched with extra information, such as Country and Season of the patch.
    See `add_full_ben_metadata` for more information.

    This tool will store all intermediate results in a temporary directory.
    This temporary directory will be printed to allow accessing these
    intermediate results if necessary.
    The resulting GeoDataFrame will be copied to `output_path`.

    The other keyword arguments should usually be left untouched.
    """
    output_path = Path(output_path).resolve()
    intermediate_dir = Path(USER_DIR)
    rich.print("[yellow]The intermediate results will be stored in: [/yellow]")
    rich.print(f"[yellow]{intermediate_dir}[/yellow]\n\n")

    rich.print("Parsing from json files")
    rich.print("This may take up to 30min for the entire dataset!")
    raw_gdf_path = build_raw_ben_s2_parquet(
        ben_path, output_path=intermediate_dir / "raw_ben_gdf.parquet", **kwargs
    )

    rich.print("Removing discouraged entries")
    gdf_path = remove_discouraged_parquet_entries(raw_gdf_path)

    if add_metadata:
        rich.print("Adding metadata")
        gdf_path = extend_ben_s2_parquet(gdf_path)

    shutil.copyfile(gdf_path, output_path)
    rich.print(f"Final result copied to {output_path}")
    return output_path


@fc.delegates(build_raw_ben_s1_parquet, but=["output_path"])
def build_recommended_s1_parquet(
    ben_path: Path,
    add_metadata: bool = True,
    output_path: Path = "final_ben_s1.parquet",
    **kwargs,
) -> Path:
    """
    Generate the recommended S1-GeoDataFrame and save
    it as a parquet file.

    It will call `build_raw_ben_s1_parquet` under the hood and remove
    patches that are not recommended for DL.
    If `add_metadata` is set, the GeoDataFrame will be
    enriched with extra information, such as Country and Season of the patch.
    See `add_full_ben_metadata` for more information.

    This tool will store all intermediate results in the default USER directory.
    This directory will be printed to allow accessing these
    intermediate results if necessary.
    The resulting GeoDataFrame will be copied to `output_path`.

    The other keyword arguments should usually be left untouched.
    """
    output_path = Path(output_path).resolve()
    intermediate_dir = Path(USER_DIR)
    rich.print("[yellow]The intermediate results will be stored in: [/yellow]")
    rich.print(f"[yellow]{intermediate_dir}[/yellow]\n\n")

    rich.print("Parsing from json files")
    rich.print("This may take up to 30min for the entire dataset!")
    raw_gdf_path = build_raw_ben_s1_parquet(
        ben_path, output_path=intermediate_dir / "raw_ben_gdf.parquet", **kwargs
    )

    rich.print("Removing discouraged entries")
    gdf_path = remove_discouraged_parquet_entries(raw_gdf_path)

    if add_metadata:
        rich.print("Adding metadata")
        gdf_path = extend_ben_s1_parquet(gdf_path)

    shutil.copyfile(gdf_path, output_path)
    rich.print(f"Final result copied to {output_path}")
    return output_path


def _run_gdf_cli() -> None:
    app = typer.Typer(rich_markup_mode="markdown")
    app.command()(build_recommended_s1_parquet)
    app.command()(build_recommended_s2_parquet)
    app.command()(build_raw_ben_s1_parquet)
    app.command()(build_raw_ben_s2_parquet)
    app.command()(extend_ben_s1_parquet)
    app.command()(extend_ben_s2_parquet)
    app.command()(remove_discouraged_parquet_entries)
    app()


if __name__ == "__main__" and not fc.IN_IPYTHON:
    _run_gdf_cli()

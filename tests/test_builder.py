from pathlib import Path

import fastcore.all as fc
import geopandas
import geopandas.testing
import pandas as pd
import pandas.testing
import pytest
from bigearthnet_common.constants import COUNTRIES, COUNTRIES_ISO_A2
from shapely.geometry import Point, Polygon, box

from bigearthnet_gdf_builder.builder import *
from bigearthnet_gdf_builder.builder import (
    _get_box_from_two_coords,
    _get_country_borders,
)


@pytest.fixture
def test_dataset_path() -> Path:
    return Path(__file__).parent.resolve() / Path("datasets/tiny/")


@pytest.fixture
def test_folder_path(test_dataset_path) -> Path:
    return test_dataset_path / "S2A_MSIL2A_20170617T113321_4_55/"


@pytest.fixture
def test_image_path(test_folder_path) -> Path:
    return test_folder_path / "S2A_MSIL2A_20170617T113321_4_55_B08.tif"


@pytest.fixture
def test_json_path(test_dataset_path) -> Path:
    return (
        test_dataset_path
        / "S2A_MSIL2A_20170617T113321_36_85"
        / "S2A_MSIL2A_20170617T113321_36_85_labels_metadata.json"
    )


@pytest.fixture
def test_json_single_label_path(test_dataset_path) -> Path:
    return (
        test_dataset_path
        / "S2A_MSIL2A_20170617T113321_4_55/"
        / "S2A_MSIL2A_20170617T113321_4_55_labels_metadata.json"
    )


# # S1A_IW_GRDH_1SDV_20170613T165043_33UUP_61_39
# test_gdf_path = (test_dataset / "tiny.parquet").resolve(strict=True)
# Want json with multiple labels!
@pytest.fixture
def test_dataset_s1_path() -> Path:
    return Path(__file__).parent.resolve() / Path("datasets/s1-tiny/")


@pytest.fixture
def test_s1_folder_path(test_dataset_s1_path) -> Path:
    return test_dataset_s1_path / "S1A_IW_GRDH_1SDV_20170613T165043_33UUP_61_39"


@pytest.fixture
def test_s1_image_path(test_s1_folder_path) -> Path:
    return test_s1_folder_path / "S1A_IW_GRDH_1SDV_20170613T165043_33UUP_61_39_VH.tif"


@pytest.fixture
def test_s1_json_path(test_dataset_s1_path) -> Path:
    return (
        test_dataset_s1_path
        / "S1A_IW_GRDH_1SDV_20170613T165043_33UUP_61_39"
        / "S1A_IW_GRDH_1SDV_20170613T165043_33UUP_61_39_labels_metadata.json"
    )


@pytest.fixture
def ben_bounds() -> geopandas.GeoSeries:
    ben_bounds_geom = box(
        minx=2.634283e06, miny=1.727067e06, maxx=5.416844e06, maxy=5.103392e06
    )
    return geopandas.GeoSeries([ben_bounds_geom], crs="EPSG:3035")


def test_get_box():
    box1 = _get_box_from_two_coords([0, 0], [2, 2])
    box2 = _get_box_from_two_coords([2, 2], [0, 0])
    box3 = _get_box_from_two_coords([0, 2], [2, 0])
    fc.test_eq(box1, box2)
    fc.test_eq(box1, box3)


def test_box_from_ul_lr_coords():
    b1 = box_from_ul_lr_coords(ulx=0, uly=4, lrx=4, lry=0)
    b2 = Polygon([[0, 0], [0, 4], [4, 4], [4, 0], [0, 0]])
    assert isinstance(b1, Polygon)
    assert b1.equals(b2)


def test_reprojection():
    north_east_crs = "epsg:2953"
    enc_point = Point(1099489.55, 9665176.75)
    tfm_points = geopandas.GeoSeries([enc_point], crs=north_east_crs).to_crs(
        epsg="4326"
    )
    long, lat = tfm_points.x[0], tfm_points.y[0]

    # _golden values_ from http://epsg.io/
    # http://epsg.io/transform#s_srs=2953&t_srs=4326&x=1099489.55&y=9665176.75
    ref_long, ref_lat = (-94.375, 63.25)
    fc.test_close([long, lat], [ref_long, ref_lat], eps=0.1)


def test_ben_s2_gdf_patch_to_gdf(test_json_path):
    gdf = ben_s2_patch_to_gdf(test_json_path)
    gdf2 = ben_s2_patch_to_gdf(test_json_path.parent)

    geopandas.testing.assert_geoseries_equal(gdf.geometry, gdf2.geometry)
    geopandas.testing.assert_geodataframe_equal(gdf, gdf2)


def test_ben_s2_gdf_patch_to_gdf_single_label(test_json_single_label_path):
    gdf = ben_s2_patch_to_gdf(test_json_single_label_path)
    assert isinstance(gdf["labels"][0], list)


def test_ben_s2_patch_reprojected_gdf(test_json_path, test_json_single_label_path):
    # silently test if appending works too
    gdf = pd.concat(
        [
            ben_s2_patch_to_reprojected_gdf(test_json_path),
            ben_s2_patch_to_reprojected_gdf(test_json_single_label_path),
        ],
        axis=0,
    )
    assert gdf.crs == "EPSG:3035"


def test_ben_s1_patch_to_gdf(test_s1_json_path):
    gdf_s1 = ben_s1_patch_to_gdf(test_s1_json_path)
    assert isinstance(gdf_s1, geopandas.GeoDataFrame)
    gdf_s1_parent = ben_s1_patch_to_gdf(test_s1_json_path.parent)

    geopandas.testing.assert_geoseries_equal(gdf_s1.geometry, gdf_s1_parent.geometry)
    geopandas.testing.assert_geodataframe_equal(gdf_s1, gdf_s1_parent)


def test_get_gdf_from_s2_patch_dir(test_dataset_path, ben_bounds):
    gdf = get_gdf_from_s2_patch_dir(test_dataset_path)
    assert gdf.within(ben_bounds.iloc[0]).all()


def test_get_gdf_from_s1_patch_dir(test_dataset_s1_path, ben_bounds):
    gdf = get_gdf_from_s1_patch_dir(test_dataset_s1_path)
    assert gdf.within(ben_bounds.iloc[0]).all()


def test_build_gdf_from_s2_patch_paths(test_folder_path):
    gdf1 = ben_s2_patch_to_reprojected_gdf(test_folder_path)
    gdf2 = build_gdf_from_s2_patch_paths([test_folder_path], n_workers=2)
    geopandas.testing.assert_geodataframe_equal(gdf1, gdf2)


def test_get_country_borders():
    countries = _get_country_borders()
    assert len(countries[countries["NAME"].isin(COUNTRIES)]) == len(COUNTRIES)
    # ensures that the iso_a2 match with my country border shapefile
    assert len(countries[countries["ISO_A2"].isin(COUNTRIES_ISO_A2)]) == len(
        COUNTRIES_ISO_A2
    )


def test_assign_to_ben_country():
    g = geopandas.GeoDataFrame(
        {
            "city": [
                "Dublin",
                "Pristina",
                "Oslo",
                "Geneva",
                "Vienna",
            ],
            "geometry": [
                Point(-6.26027, 53.34976),
                Point(21.27082, 42.69962),
                Point(24.94275, 60.16749),
                Point(6.14392, 46.22565),
                Point(16.37122, 48.22021),
            ],
        },
        crs="epsg:4326",
    )

    assigned_gdf = assign_to_ben_country(g)
    assert assigned_gdf["country"].tolist() == [
        "Ireland",
        "Kosovo",
        "Finland",
        "Switzerland",
        "Austria",
    ]


def test_tfm_month_to_season():
    dates = pd.Series(
        [
            "2018-01-21",
            "2018-04-21",
            "2018-08-10",
            "2017-10-27",
        ]
    )
    assert tfm_month_to_season(dates).to_list() == [
        Season.Winter,
        Season.Spring,
        Season.Summer,
        Season.Fall,
    ]


def test_filter_season():
    dates_df = pd.DataFrame(
        {
            "Date": [
                "2018-01-21",
                "2018-04-21",
                "2018-08-10",
                "2017-10-27",
            ]
        }
    )
    pandas.testing.assert_frame_equal(
        filter_season(dates_df, "Date", Season.Winter).reset_index(drop=True),
        pd.DataFrame({"Date": ["2018-01-21"]}),
    )
    pandas.testing.assert_frame_equal(
        filter_season(dates_df, "Date", Season.Fall).reset_index(drop=True),
        pd.DataFrame({"Date": ["2017-10-27"]}),
    )


# FUTURE: Add tests that better test the functionality
def test_add_full_ben_s2_metadata(test_dataset_path):
    gdf = get_gdf_from_s2_patch_dir(test_dataset_path)
    metadata_gdf = add_full_ben_s2_metadata(gdf)
    metadata_cols = {"snow", "cloud_or_shadow", "original_split", "country", "season"}
    assert set(metadata_gdf.columns.to_list()) & metadata_cols == metadata_cols


def test_add_full_ben_s1_metadata(test_dataset_s1_path):
    gdf = get_gdf_from_s1_patch_dir(test_dataset_s1_path)
    metadata_gdf = add_full_ben_s1_metadata(gdf)
    metadata_cols = {"snow", "cloud_or_shadow", "original_split", "country", "season"}
    assert set(metadata_gdf.columns.to_list()) & metadata_cols == metadata_cols


# TODO: Manually add some negative examples!
def test_remove_bad_ben_gdf_entries(test_dataset_path):
    gdf1 = get_gdf_from_s2_patch_dir(test_dataset_path)
    gdf2 = remove_bad_ben_gdf_entries(gdf1)
    geopandas.testing.assert_geodataframe_equal(gdf1, gdf2)


def test_remove_bad_ben_gdf_entries(test_dataset_s1_path):
    gdf1 = get_gdf_from_s1_patch_dir(test_dataset_s1_path)
    gdf2 = remove_bad_ben_gdf_entries(gdf1)
    geopandas.testing.assert_geodataframe_equal(gdf1, gdf2)


# TODO: Better test the written files!
def test_build_recommended_s2_parquet(tmp_path, test_dataset_path):
    t = build_recommended_s2_parquet(
        test_dataset_path, output_path=tmp_path / "out.parquet"
    )
    assert t.stat().st_size > 0


def test_build_raw_s2_parquet(tmp_path, test_dataset_path):
    p = build_raw_ben_s2_parquet(
        test_dataset_path, output_path=tmp_path / "raw_ben_gdf.parquet"
    )
    assert p.stat().st_size > 0


def test_build_recommended_s1_parquet(tmp_path, test_dataset_s1_path):
    t = build_recommended_s1_parquet(
        test_dataset_s1_path, output_path=tmp_path / "out.parquet"
    )
    assert t.stat().st_size > 0


def test_build_raw_s1_parquet(tmp_path, test_dataset_s1_path):
    p = build_raw_ben_s1_parquet(
        test_dataset_s1_path, output_path=tmp_path / "raw_ben_gdf.parquet"
    )
    assert p.stat().st_size > 0

import pandas as pd

from eki_walk.territory.readings import match_readings, station_place_rows


def test_match_readings_by_name_and_distance():
    groups = pd.DataFrame({"name": ["高円寺", "早稲田", "早稲田", "新駅"], "x": [0.0, 5000.0, 5700.0, 9000.0], "y": [0.0, 0.0, 0.0, 0.0]})
    osm = pd.DataFrame(
        {
            "name": ["高円寺", "高円寺", "早稲田", "早稲田", "早稲田"],
            "hira": ["こうえんじ", None, "わせだ", None, "わせだ"],
            "x": [100.0, 50.0, 5050.0, 5600.0, 5750.0],
            "y": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    r = match_readings(groups, osm, max_m=1500)
    assert r == {0: "こうえんじ", 1: "わせだ", 2: "わせだ"}  # 新駅 has no OSM match


def test_far_or_differently_named_nodes_are_ignored():
    groups = pd.DataFrame({"name": ["大塚"], "x": [0.0], "y": [0.0]})
    osm = pd.DataFrame({"name": ["大塚", "大塚駅前"], "hira": ["おおつか", "おおつかえきまえ"], "x": [3000.0, 10.0], "y": [0.0, 0.0]})
    assert match_readings(groups, osm, max_m=1500) == {}


def test_station_place_rows_replace_ekiwalk_station_rows():
    places = [["杉並区高円寺南１丁目", "スギナミク", 139.65, 35.70, "t"], ["高円寺駅", "", 139.649, 35.705, "s"]]
    stations = [{"id": 0, "name": "高円寺", "lon": 139.6495, "lat": 35.7054}]
    out = station_place_rows(places, stations, {0: "こうえんじ"})
    assert out[0] == places[0]
    assert out[1] == ["高円寺駅", "こうえんじえき", 139.6495, 35.7054, "s"]


def test_names_are_compared_after_normalising_ke_and_brackets():
    from eki_walk.territory.readings import norm_name

    assert norm_name("阿佐ヶ谷") == norm_name("阿佐ケ谷") == norm_name("阿佐ヵ谷")
    assert norm_name("明治神宮前〈原宿〉") == norm_name("明治神宮前")
    assert norm_name("押上（スカイツリー前）") == norm_name("押上")
    groups = pd.DataFrame({"name": ["阿佐ヶ谷"], "x": [0.0], "y": [0.0]})
    osm = pd.DataFrame({"name": ["阿佐ケ谷"], "hira": ["あさがや"], "x": [10.0], "y": [0.0]})
    assert match_readings(groups, osm, max_m=1500) == {0: "あさがや"}


def test_town_readings_fill_the_gaps():
    from eki_walk.territory.readings import town_readings

    towns = [
        {"oaza_cho": "中目黒", "oaza_cho_kana": "ナカメグロ"},
        {"oaza_cho": "大塚", "oaza_cho_kana": "オオツカ"},
        {"oaza_cho": "大塚", "oaza_cho_kana": "オオツカ"},
        {"oaza_cho": "日本橋", "oaza_cho_kana": "ニホンバシ"},
        {"oaza_cho": "日本橋", "oaza_cho_kana": "ニッポンバシ"},  # ambiguous: not used
    ]
    assert town_readings(towns) == {"中目黒": "ナカメグロ", "大塚": "オオツカ"}


def test_city_names_also_give_readings():
    from eki_walk.territory.readings import town_readings

    towns = [
        {"city": "春日部市", "city_kana": "カスカベシ", "oaza_cho": "粕壁", "oaza_cho_kana": "カスカベ"},
        {"city": "狭山市", "city_kana": "サヤマシ", "oaza_cho": "入間川", "oaza_cho_kana": "イルマガワ"},
    ]
    r = town_readings(towns)
    assert r["春日部"] == "カスカベ" and r["狭山市"] == "サヤマシ" and r["狭山"] == "サヤマ"
    assert r["粕壁"] == "カスカベ"


def test_nodes_without_a_name_are_ignored():
    from eki_walk.territory.readings import norm_name

    assert norm_name(float("nan")) == ""
    assert norm_name(None) == ""
    groups = pd.DataFrame({"name": ["横浜"], "x": [0.0], "y": [0.0]})
    osm = pd.DataFrame({"name": [float("nan"), "横浜"], "hira": ["なにか", "よこはま"], "x": [5.0, 10.0], "y": [0.0, 0.0]})
    assert match_readings(groups, osm, max_m=1500) == {0: "よこはま"}

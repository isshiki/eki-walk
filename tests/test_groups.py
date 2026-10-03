import pandas as pd

from eki_walk.territory.groups import display_line, merge_groups


def rows():
    return pd.DataFrame(
        {
            "group": ["a", "a", "b", "c", "d", "e"],
            "name": ["池袋", "池袋", "池袋", "早稲田", "早稲田", "目白"],
            "line": ["山手線", "山手線", "13号線副都心線", "荒川線", "5号線東西線", "山手線"],
            "operator": ["東日本旅客鉄道", "東日本旅客鉄道", "東京地下鉄", "東京都", "東京地下鉄", "東日本旅客鉄道"],
            "x": [0.0, 10.0, 361.0, 0.0, 744.0, 100.0],
            "y": [0.0, 0.0, 0.0, 5000.0, 5000.0, 2000.0],
        }
    )


def test_same_name_within_600m_is_merged():
    row_group, g = merge_groups(rows(), 600)
    assert row_group[0] == row_group[1] == row_group[2]
    assert row_group[3] != row_group[4]  # 早稲田 744 m apart stays separate
    assert len(g) == 4
    ike = g.loc[row_group[0]]
    assert ike["name"] == "池袋"
    assert [x["line"] for x in ike["lines"]] == ["副都心線", "山手線"]
    assert ike["members"] == [0, 1, 2]
    assert ike["key"] == "a|b"  # same N02 groups -> same key in every region
    assert g.loc[row_group[3], "key"] == "c"


def test_different_names_are_not_merged():
    row_group, _ = merge_groups(rows(), 10_000)
    assert row_group[5] != row_group[0]


def test_display_line():
    assert display_line("4号線丸ノ内線") == "丸ノ内線"
    assert display_line("中央線") == "中央線"
    assert display_line("1号線") == "1号線"

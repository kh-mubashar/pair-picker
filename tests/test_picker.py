from picker import RULES, build, hl_name


def test_k_prefix_and_plain_names():
    names = {"BTC", "kPEPE"}
    assert hl_name("BTC", names) == "BTC"
    assert hl_name("PEPE", names) == "kPEPE"
    assert hl_name("XYZ", names) is None


def test_buyable_needs_rank_volume_and_testnet():
    syms = ["BTC", "ETH", "AAA", "BBB"]
    vol = {"BTC": 5e9, "ETH": 2e9, "AAA": 5e5, "BBB": 3e6}
    test = {"BTC", "AAA", "BBB"}            # ETH missing on testnet
    rules = dict(RULES, top_n=3, hold_rank=4)
    c = {x["hl_name"]: x for x in build(syms, vol, test, rules)}
    assert c["BTC"]["buyable"]
    assert not c["ETH"]["buyable"]         # not listed on testnet
    assert not c["AAA"]["buyable"]         # volume under $1M
    assert not c["BBB"]["buyable"]         # rank 4 > top_n 3: held only
    assert c["BBB"]["rank"] == 4


def test_coin_not_on_hyperliquid_is_skipped_but_rank_kept():
    c = build(["BTC", "NOTHL", "ETH"], {"BTC": 1e9, "ETH": 1e9}, {"BTC", "ETH"})
    assert [x["hl_name"] for x in c] == ["BTC", "ETH"]
    assert c[1]["rank"] == 3

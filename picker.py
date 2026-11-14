"""pair-picker: the daily coin list shared by the bot and ATLAS. Plain code, no AI, no trading.

Each run writes lists/YYYY-MM-DD.json and lists/latest.json:
  1. CoinGecko's coins by market cap, stablecoins removed, ranked 1, 2, 3, ...
  2. Each coin matched to its Hyperliquid name (BTC, or kPEPE for coins Hyperliquid lists per 1,000 units).
  3. Volume is read from Hyperliquid MAINNET (the real market; testnet volume is not meaningful).
     Listing is checked on Hyperliquid TESTNET (where the bot and ATLAS place their orders).
  4. A coin is "buyable" when it is in the top 100, trades at least $1M a day on mainnet and is listed on testnet.
     Coins ranked 101 to 120 are included too (buyable = false) so the bot can apply its hold buffer.

If any source fails, nothing is written and the run fails: readers keep the previous list and must check its date.

Usage: python picker.py [--out lists] [--date YYYY-MM-DD]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

RULES = dict(top_n=100, hold_rank=120, min_volume_usd=1_000_000,
             rank_source="coingecko market cap, stablecoins removed",
             volume_venue="hyperliquid-mainnet", listing_venue="hyperliquid-testnet")
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
HL_MAINNET = "https://api.hyperliquid.xyz/info"
HL_TESTNET = "https://api.hyperliquid-testnet.xyz/info"
# Same list the bot used before the restructure, so rankings stay comparable.
STABLES = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "TUSD", "USDD", "PYUSD", "USDS", "USD1", "USDP", "GUSD",
           "FRAX", "USDB", "EURC", "RLUSD", "BUSD", "USDT0", "SUSDE", "USDX", "USDG", "USDF", "USDO", "BFUSD",
           "LUSD", "CRVUSD", "GHO", "USDY", "USTB", "BUIDL", "USYC", "SUSDS", "EURS", "XAUT", "PAXG"}


class PickerError(Exception):
    pass


def _get(fn, what, tries=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # network or bad response: retry, then fail loudly
            last = e
            time.sleep(10 * (i + 1))
    raise PickerError(f"{what} failed after {tries} tries: {str(last)[:200]}")


def coingecko_symbols(n_needed):
    def call():
        r = requests.get(COINGECKO_URL, params=dict(vs_currency="usd", order="market_cap_desc", per_page=250, page=1),
                         timeout=30)
        r.raise_for_status()
        return r.json()
    rows = _get(call, "CoinGecko")
    out = []
    for c in rows:
        sym = (c.get("symbol") or "").upper()
        if sym and sym not in STABLES and sym not in out:
            out.append(sym)
    if len(out) < n_needed:
        raise PickerError(f"CoinGecko returned only {len(out)} coins, need {n_needed}")
    return out[:n_needed]


def hl_post(url, body, what):
    def call():
        r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    return _get(call, what)


def mainnet_volumes():
    meta, ctxs = hl_post(HL_MAINNET, {"type": "metaAndAssetCtxs"}, "Hyperliquid mainnet")
    return {a["name"]: float(c.get("dayNtlVlm") or 0) for a, c in zip(meta["universe"], ctxs)
            if not a.get("isDelisted")}


def testnet_names():
    meta = hl_post(HL_TESTNET, {"type": "meta"}, "Hyperliquid testnet")
    return {a["name"] for a in meta["universe"] if not a.get("isDelisted")}


def hl_name(sym, names):
    if sym in names:
        return sym
    if "k" + sym in names:   # Hyperliquid lists very cheap coins per 1,000 units, e.g. kPEPE
        return "k" + sym
    return None


def build(symbols, vol_main, on_test, rules=RULES):
    coins, seen = [], set()
    for rank, sym in enumerate(symbols[:rules["hold_rank"]], start=1):
        name = hl_name(sym, vol_main) or hl_name(sym, on_test)
        if not name or name in seen:
            continue
        seen.add(name)
        vol = vol_main.get(name)
        coins.append(dict(rank=rank, symbol=sym, hl_name=name,
                          mainnet_volume_usd=round(vol, 0) if vol is not None else None,
                          on_mainnet=name in vol_main, on_testnet=name in on_test,
                          buyable=bool(rank <= rules["top_n"] and (vol or 0) >= rules["min_volume_usd"]
                                       and name in on_test)))
    return coins


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="lists")
    ap.add_argument("--date", default=None, help="label for the file (default: today, UTC)")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    day = a.date or now.strftime("%Y-%m-%d")
    try:
        symbols = coingecko_symbols(RULES["hold_rank"])
        vol_main = mainnet_volumes()
        on_test = testnet_names()
    except PickerError as e:
        print(f"FAILED, nothing written: {e}", file=sys.stderr)
        return 1
    coins = build(symbols, vol_main, on_test)
    doc = dict(date=day, generated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"), rules=RULES,
               counts=dict(ranked=len(symbols), on_hyperliquid=len(coins),
                           buyable=sum(c["buyable"] for c in coins)),
               coins=coins)
    os.makedirs(a.out, exist_ok=True)
    body = json.dumps(doc, indent=1) + "\n"
    for name in (f"{day}.json", "latest.json"):
        with open(os.path.join(a.out, name), "w") as f:
            f.write(body)
    print(f"{day}: {doc['counts']['buyable']} buyable coins, {len(coins)} on Hyperliquid within rank "
          f"{RULES['hold_rank']}")
    for c in coins:
        print(f"  {c['rank']:>3} {c['hl_name']:<10} vol ${c['mainnet_volume_usd'] or 0:>16,.0f} "
              f"testnet={'yes' if c['on_testnet'] else 'no ':<3} {'BUYABLE' if c['buyable'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# pair-picker

The daily coin list shared by the bot (`gc-hl-bot`) and ATLAS. It is the only thing the two systems share.
Plain code, no AI, no keys, no trading.

## What it does

Every day at 00:05 UTC (`.github/workflows/pick.yml`) it writes `lists/YYYY-MM-DD.json` and `lists/latest.json`:

1. Coins ranked by market cap from CoinGecko, with stablecoins removed.
2. Each coin is matched to its Hyperliquid name (`BTC`, or `kPEPE` for coins listed per 1,000 units).
3. **Volume** comes from Hyperliquid **mainnet** (the real market). **Listing** is checked on Hyperliquid **testnet**,
   where the orders are placed.
4. `buyable: true` means: rank 100 or better, at least $1M traded a day on mainnet, and listed on testnet.
   Coins ranked 101 to 120 are included with `buyable: false`, so the bot can keep holding a coin until it falls
   below rank 120.

If CoinGecko or Hyperliquid fails, nothing is written and the run fails. Readers keep using the previous list and
must check its `date`.

## File format

```json
{"date": "2026-11-15", "generated_at": "2026-11-15T00:05:41Z",
 "rules": {"top_n": 100, "hold_rank": 120, "min_volume_usd": 1000000, ...},
 "counts": {"ranked": 120, "on_hyperliquid": 97, "buyable": 71},
 "coins": [{"rank": 1, "symbol": "BTC", "hl_name": "BTC", "mainnet_volume_usd": 2100000000,
            "on_mainnet": true, "on_testnet": true, "buyable": true}, ...]}
```

## Readers

- `gc-hl-bot` and ATLAS read this repo; neither writes to it.
- This repo never reads either of them.

## Run it yourself

```bash
pip install requests pytest
python -m pytest -q
python picker.py --out lists
```

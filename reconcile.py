"""
On-chain vs ledger reconciliation.

Source A: on-chain export (Etherscan / Solscan CSV, or API pull)
Source B: internal ledger (exchange withdrawal/deposit history CSV, or your own log)

Output:
  breaks.csv   - every unmatched or mismatched item, with a break reason
  summary.txt  - counts by break type (this is what goes on the CV)

Usage:
  python reconcile.py onchain.csv ledger.csv

Expected columns (rename in COLMAP below if yours differ):
  onchain.csv : Txhash, DateTime (UTC), From, To, Value_IN(ETH), Value_OUT(ETH), TxnFee(ETH), Status
  ledger.csv  : txid, date, direction, amount, fee, status
                (direction = in/out; drop the column if amounts are already signed)
"""

import sys
from decimal import Decimal, InvalidOperation

import pandas as pd

# --- tolerances: anything below these is NOT a break -------------------------
AMOUNT_TOLERANCE = Decimal("0.000001")   # rounding / display precision
TIME_TOLERANCE_HOURS = 24                # block time vs booking time

COLMAP_ONCHAIN = {
    "hash": "Txhash",
    "time": "DateTime (UTC)",
    "in": "Value_IN(ETH)",
    "out": "Value_OUT(ETH)",
    "fee": "TxnFee(ETH)",
    "status": "Status",
}

COLMAP_LEDGER = {
    "hash": "txid",
    "time": "date",
    "amount": "amount",
    "direction": "direction",
    "fee": "fee",
    "status": "status",
}


def to_dec(x):
    try:
        return Decimal(str(x).replace(",", "").strip() or "0")
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def norm_hash(x):
    return str(x).strip().lower()


def load(path, colmap, side):
    df = pd.read_csv(path)
    missing = [c for c in colmap.values() if c not in df.columns]
    if missing:
        sys.exit(f"{path}: missing columns {missing}\nfound: {list(df.columns)}")
    out = pd.DataFrame()
    out["hash"] = df[colmap["hash"]].map(norm_hash)
    out["time"] = pd.to_datetime(df[colmap["time"]], utc=True, errors="coerce")
    if side == "onchain":
        out["amount"] = df[colmap["in"]].map(to_dec) - df[colmap["out"]].map(to_dec)
    else:
        amt = df[colmap["amount"]].map(to_dec)
        direction = df[colmap["direction"]] if "direction" in colmap else None
        out["amount"] = amt if direction is None else [
            a if str(d).lower().startswith(("in", "dep", "cred")) else -a
            for a, d in zip(amt, direction)
        ]
    out["fee"] = df[colmap["fee"]].map(to_dec)
    out["status"] = df[colmap["status"]].fillna("").astype(str).str.lower()
    out["source"] = side
    return out


def reconcile(onchain, ledger):
    breaks = []

    dup_a = onchain[onchain.duplicated("hash", keep=False)]
    for _, r in dup_a.iterrows():
        breaks.append({**r.to_dict(), "break_type": "DUPLICATE_ON_CHAIN"})

    a = onchain.drop_duplicates("hash").set_index("hash")
    b = ledger.drop_duplicates("hash").set_index("hash")

    only_chain = a.index.difference(b.index)
    only_ledger = b.index.difference(a.index)
    both = a.index.intersection(b.index)

    for h in only_chain:
        r = a.loc[h]
        reason = "FAILED_TX_ON_CHAIN_ONLY" if "fail" in r["status"] else "MISSING_IN_LEDGER"
        breaks.append({"hash": h, **r.to_dict(), "break_type": reason})

    for h in only_ledger:
        r = b.loc[h]
        breaks.append({"hash": h, **r.to_dict(), "break_type": "MISSING_ON_CHAIN"})

    for h in both:
        ra, rb = a.loc[h], b.loc[h]
        diff = ra["amount"] - rb["amount"]
        if abs(diff) > AMOUNT_TOLERANCE:
            btype = "FEE_NOT_BOOKED" if abs(abs(diff) - ra["fee"]) <= AMOUNT_TOLERANCE else "AMOUNT_MISMATCH"
            breaks.append({
                "hash": h, "amount_onchain": ra["amount"], "amount_ledger": rb["amount"],
                "diff": diff, "break_type": btype,
            })
        if pd.notna(ra["time"]) and pd.notna(rb["time"]):
            gap = abs((ra["time"] - rb["time"]).total_seconds()) / 3600
            if gap > TIME_TOLERANCE_HOURS:
                breaks.append({
                    "hash": h, "time_onchain": ra["time"], "time_ledger": rb["time"],
                    "gap_hours": round(gap, 1), "break_type": "TIMING_DIFFERENCE",
                })
        if "fail" in ra["status"] and "fail" not in rb["status"]:
            breaks.append({"hash": h, "break_type": "FAILED_TX_BOOKED_AS_SETTLED"})

    return pd.DataFrame(breaks)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)

    onchain = load(sys.argv[1], COLMAP_ONCHAIN, "onchain")
    ledger = load(sys.argv[2], COLMAP_LEDGER, "ledger")
    breaks = reconcile(onchain, ledger)

    total = len(onchain)
    broken_hashes = set(breaks["hash"]) if not breaks.empty else set()
    matched = len(set(onchain["hash"]) - broken_hashes)
    lines = [
        f"Transactions on chain      : {total}",
        f"Records in ledger          : {len(ledger)}",
        f"Breaks identified          : {len(breaks)}",
        f"Clean match rate           : {matched / total:.1%}" if total else "",
        "",
        "Breaks by type:",
    ]
    if not breaks.empty:
        for k, v in breaks["break_type"].value_counts().items():
            lines.append(f"  {k:<32} {v}")
        breaks.to_csv("breaks.csv", index=False)

    report = "\n".join(lines)
    print(report)
    with open("summary.txt", "w") as fh:
        fh.write(report + "\n")


if __name__ == "__main__":
    main()

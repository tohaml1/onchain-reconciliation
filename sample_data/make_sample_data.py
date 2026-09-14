"""
Generates synthetic test data for reconcile.py.

The data is fabricated, not real wallet activity. Break types are planted
deliberately so the classification logic can be verified against a known answer:

  4 x transaction settled on chain, absent from the ledger
  3 x gas fee not booked
  2 x ledger entry that never settled on chain
  2 x failed transaction booked as settled
  2 x booking date past the timing tolerance
  1 x amount mismatch (decimals error)

Run:  python sample_data/make_sample_data.py
"""

import csv
import datetime as dt
import pathlib
import random

random.seed(7)
OUT = pathlib.Path(__file__).parent
START = dt.datetime(2026, 3, 1, 9, 0)


def tx_hash(i):
    return "0x" + format(i, "064x")


def build():
    onchain, ledger = [], []
    for i in range(1, 61):
        ts = START + dt.timedelta(hours=i * 7)
        incoming = i % 3 == 0
        amount = round(random.uniform(0.05, 4.0), 6)
        fee = round(random.uniform(0.0008, 0.004), 6)

        onchain.append({
            "Txhash": tx_hash(i),
            "DateTime (UTC)": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "From": "0xaaa" if incoming else "0xme",
            "To": "0xme" if incoming else "0xbbb",
            "Value_IN(ETH)": amount if incoming else 0,
            "Value_OUT(ETH)": 0 if incoming else amount,
            "TxnFee(ETH)": fee,
            "Status": "Fail" if i in (11, 34) else "",
        })

        if i in (7, 19, 41, 52):          # never reaches the ledger
            continue

        led_amount, led_fee, led_ts = amount, fee, ts
        if i in (5, 23, 47):              # gas fee not booked
            led_amount, led_fee = round(amount - fee, 6), 0
        if i in (14, 38):                 # booked days later
            led_ts = ts + dt.timedelta(days=3)
        if i == 29:                       # decimals misread
            led_amount = round(amount * 10, 6)

        ledger.append({
            "txid": tx_hash(i),
            "date": led_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": "in" if incoming else "out",
            "amount": led_amount,
            "fee": led_fee,
            "status": "ok",
        })

    for j in (901, 902):                  # booked, never settled
        ledger.append({
            "txid": tx_hash(j), "date": "2026-04-02 12:00:00",
            "direction": "out", "amount": 0.35, "fee": 0, "status": "ok",
        })

    return onchain, ledger


def write(rows, path):
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name}: {len(rows)} rows")


if __name__ == "__main__":
    onchain, ledger = build()
    write(onchain, OUT / "onchain_sample.csv")
    write(ledger, OUT / "ledger_sample.csv")

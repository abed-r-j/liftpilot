"""Live context feeds (free, no API key) with an offline cache.

Two feeds have a real job in the optimizer; neither changes the uplift scores:

* **Exchange rates** (Frankfurter, central-bank reference rates): a budget
  given in the decision-maker's currency (the course brief uses Brazilian
  reais) becomes a constraint in the data's currency, and results are reported
  back in that currency at today's rate.
* **Public holidays** (Nager.Date): the send date and the measurement window
  of the next campaign are moved off public holidays, which would otherwise
  distort the treated-versus-holdout comparison.

Every call has a short timeout. The last good answer is cached on disk and is
used, clearly labelled with its date, when there is no connection.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from liftpilot import config

FX_URL = "https://api.frankfurter.dev/v2/rates"
FX_FALLBACK_URL = "https://open.er-api.com/v6/latest/{base}"
HOLIDAY_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
TIMEOUT = 4.0


def _cache_file(name: str) -> Path:
    path = config.cache_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{name}.json"


def _save(name: str, payload: Any) -> None:
    _cache_file(name).write_text(
        json.dumps(
            {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "payload": payload}
        )
    )


def _load(name: str) -> tuple[Any, str] | None:
    path = _cache_file(name)
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    return blob["payload"], blob["fetched_at"]


def _get_json(url: str, params: dict[str, str] | None = None) -> Any:
    r = httpx.get(url, params=params, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def exchange_rates(base: str, quotes: list[str], offline: bool = False) -> dict[str, Any]:
    """Units of each quote currency per one unit of ``base``."""
    base = base.upper()
    quotes = [q.upper() for q in quotes if q.upper() != base]
    name = f"fx_{base}"
    rates: dict[str, float] = {}
    source, as_of, live = "", "", False
    if not offline:
        try:
            rows = _get_json(FX_URL, {"base": base, "quotes": ",".join(quotes)})
            rates = {r["quote"]: float(r["rate"]) for r in rows}
            as_of = rows[0]["date"] if rows else ""
            source, live = "Frankfurter (central-bank reference rates)", True
        except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError):
            try:
                blob = _get_json(FX_FALLBACK_URL.format(base=base))
                rates = {q: float(blob["rates"][q]) for q in quotes if q in blob["rates"]}
                as_of = str(blob.get("time_last_update_utc", ""))
                source, live = "open.er-api.com", True
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                rates = {}
    if rates:
        cached = _load(name)
        merged = {**(cached[0]["rates"] if cached else {}), **rates}
        _save(name, {"rates": merged, "as_of": as_of, "source": source})
    else:
        cached = _load(name)
        if cached is None:
            return {"base": base, "rates": {}, "live": False, "error": "no connection and no cache"}
        payload, fetched = cached
        rates = {q: payload["rates"][q] for q in quotes if q in payload["rates"]}
        as_of, source = payload.get("as_of", ""), f"{payload.get('source', '')} (cached {fetched})"
    return {"base": base, "rates": rates, "as_of": as_of, "source": source, "live": live}


def convert(
    amount: float, from_currency: str, to_currency: str, offline: bool = False
) -> dict[str, Any]:
    if from_currency.upper() == to_currency.upper():
        return {"amount": amount, "currency": to_currency.upper(), "rate": 1.0, "live": True}
    fx = exchange_rates(from_currency, [to_currency], offline=offline)
    rate = fx["rates"].get(to_currency.upper())
    if rate is None:
        return {"error": f"no rate for {from_currency}->{to_currency}", **fx}
    return {
        "amount": round(amount * rate, 2),
        "currency": to_currency.upper(),
        "rate": rate,
        "from": {"amount": amount, "currency": from_currency.upper()},
        "as_of": fx["as_of"],
        "source": fx["source"],
        "live": fx["live"],
    }


def public_holidays(country: str, year: int, offline: bool = False) -> dict[str, Any]:
    country = country.upper()
    name = f"holidays_{country}_{year}"
    if not offline:
        try:
            rows = _get_json(HOLIDAY_URL.format(year=year, country=country))
            days = [{"date": r["date"], "name": r["name"]} for r in rows]
            _save(name, days)
            return {
                "country": country,
                "year": year,
                "holidays": days,
                "live": True,
                "source": "Nager.Date",
            }
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass
    cached = _load(name)
    if cached is None:
        return {
            "country": country,
            "year": year,
            "holidays": [],
            "live": False,
            "error": "no connection and no cache",
        }
    return {
        "country": country,
        "year": year,
        "holidays": cached[0],
        "live": False,
        "source": f"Nager.Date (cached {cached[1]})",
    }


def schedule_send(
    country: str, earliest: date | None = None, window_days: int = 14, offline: bool = False
) -> dict[str, Any]:
    """First working day on or after ``earliest`` that is not a public holiday,
    plus the holidays that fall inside the measurement window."""
    start = earliest or (datetime.now(UTC).date() + timedelta(days=1))
    days: dict[str, str] = {}
    live = True
    source = ""
    for year in {start.year, (start + timedelta(days=window_days + 10)).year}:
        res = public_holidays(country, year, offline=offline)
        live = live and bool(res.get("live"))
        source = res.get("source", source)
        days.update({h["date"]: h["name"] for h in res["holidays"]})
    send = start
    skipped = []
    while send.weekday() >= 5 or send.isoformat() in days:
        skipped.append(
            {
                "date": send.isoformat(),
                "reason": days.get(send.isoformat(), "weekend"),
            }
        )
        send += timedelta(days=1)
    window_end = send + timedelta(days=window_days)
    inside = [
        {"date": d, "name": n}
        for d, n in sorted(days.items())
        if send.isoformat() < d <= window_end.isoformat()
    ]
    return {
        "country": country.upper(),
        "earliest_requested": start.isoformat(),
        "recommended_send_date": send.isoformat(),
        "skipped_days": skipped,
        "measurement_window": [send.isoformat(), window_end.isoformat()],
        "holidays_inside_window": inside,
        "note": (
            "Holidays inside the window affect contacted and hold-out customers alike, so the "
            "comparison stays fair; they only make the effect noisier."
            if inside
            else "No public holiday inside the measurement window."
        ),
        "calendar_known": bool(days),
        "live": live,
        "source": source,
    }

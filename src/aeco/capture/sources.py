"""Sources that are actively losing history. Capture is business-daily."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional


@dataclass(frozen=True)
class CaptureSource:
    name: str
    url: str
    artifact: str
    validator: Optional[Callable[[bytes], bool]] = None


DOP = "https://f51561ras5.execute-api.us-west-2.amazonaws.com/production"
TCX = "https://www.tccustomerexpress.com"
GA = "https://www.gasalberta.com/actions/charts/default"


def _gdsr_url() -> str:
    # Filename date is the PUBLICATION date; content is the PRIOR gas day.
    return f"{TCX}/gdsr/GdsrNGTLMetric{datetime.now(timezone.utc):%Y%m%d}.csv"


def _json_ok(b: bytes) -> bool:
    return b.lstrip().startswith((b"{", b"["))


SOURCES = [
    CaptureSource("gasalberta_futures", f"{GA}?id=aeco_c_futures", "curve.json", _json_ok),
    CaptureSource("gasalberta_index_current", f"{GA}?id=aeco_ng_current", "index.json", _json_ok),
    CaptureSource("gasalberta_index_prior", f"{GA}?id=aeco_ng_prior", "index_prior.json", _json_ok),
    CaptureSource("ngtldash", f"{TCX}/alberta/dashboard/ngtldash.csv", "ngtldash.csv"),
    CaptureSource("dop_publisheddates", f"{DOP}/outages/publisheddates", "publisheddates.json", _json_ok),
    CaptureSource("dop_chart", f"{DOP}/chart/csv", "chart.csv"),
    CaptureSource("gdsr", _gdsr_url(), "gdsr.csv"),
    CaptureSource("dobenergy", "https://www.dobenergy.com/data/markets/prices/", "prices.html"),
]

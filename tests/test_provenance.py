"""Weather fingerprints record consumed payloads and preserve optional API behaviour."""

import hashlib
import json

from test_pipeline import STATION_ID, YEAR, FakeClient

from smhi2epw import EPWConfig, compile_epw
from smhi2epw.ingestion import CachedClient


def test_optional_provenance_with_custom_client_is_honest(tmp_path):
    output = tmp_path / "weather.epw"
    receipt = tmp_path / "weather.json"
    cfg = EPWConfig(
        year=YEAR,
        output_path=str(output),
        station_id=STATION_ID,
        provenance_path=str(receipt),
    )
    result = compile_epw(cfg, client=FakeClient())
    saved = json.loads(receipt.read_text())
    assert saved["epw_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert saved["result"]["rows"] == result.rows
    assert not saved["raw_response_receipts_complete"]
    assert saved["source_code_sha256"]["processing.py"]


def test_receipts_only_include_payloads_actually_read_from_shared_cache(tmp_path):
    client = CachedClient(cache_dir=str(tmp_path))
    url = "https://opendata.smhi.se/example"
    from pathlib import Path

    Path(client._cache_path(url, "json")).write_text('{"value":42}')
    (tmp_path / "unrelated.json").write_text("secret unrelated payload")
    assert client.get_json(url) == {"value": 42}
    receipts = list(client.response_receipts.values())
    assert len(receipts) == 1
    assert receipts[0]["cached"]
    assert receipts[0]["sha256"] == hashlib.sha256(b'{"value":42}').hexdigest()

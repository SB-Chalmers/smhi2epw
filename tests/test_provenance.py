"""Weather fingerprints record consumed payloads and preserve optional API behaviour."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
from test_pipeline import STATION_ID, YEAR, FakeClient

from smhi2epw import EPWConfig, compile_epw
from smhi2epw.ingestion import CachedClient
from smhi2epw.provenance import write_provenance


@dataclass
class _ReceiptResult:
    output_path: str
    rows: int = 8760


class _RecordingFakeClient(CachedClient):
    def __init__(self):
        super().__init__(cache_dir=None)
        self.fixture = FakeClient()

    def get_text(self, url, suffix="txt"):
        text = self.fixture.get_text(url, suffix)
        self._record_response(url, suffix, text, cached=False)
        return text

    def get_json(self, url):
        payload = self.fixture.get_json(url)
        self._record_response(url, "json", json.dumps(payload), cached=False)
        return payload


def _save_receipt(tmp_path, client, label="weather"):
    output = tmp_path / f"{label}.epw"
    output.write_text("EPW artifact preserved independently", encoding="utf-8")
    receipt = tmp_path / f"{label}.json"
    config = EPWConfig(YEAR, str(output), provenance_path=str(receipt), city="Göteborg")
    return write_provenance(config, _ReceiptResult(str(output)), client)


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
    assert saved["raw_responses"] == []
    assert saved["source_code_sha256"]["processing.py"]
    from importlib.metadata import version

    assert saved["pvlib_version"] == version("pvlib")


def test_receipts_only_include_payloads_actually_read_from_shared_cache(tmp_path):
    client = CachedClient(cache_dir=str(tmp_path))
    url = "https://opendata.smhi.se/example"
    Path(client._cache_path(url, "json")).write_text('{"value":42}')
    (tmp_path / "unrelated.json").write_text("secret unrelated payload")
    assert client.get_json(url) == {"value": 42}
    receipts = list(client.response_receipts.values())
    assert len(receipts) == 1
    assert receipts[0]["cached"]
    assert receipts[0]["sha256"] == hashlib.sha256(b'{"value":42}').hexdigest()


def test_unscoped_custom_receipt_collection_is_omitted(tmp_path):
    client = FakeClient()
    client.response_receipts = {
        "old": {"url": "https://previous.example", "sha256": "unrelated"}
    }

    saved = _save_receipt(tmp_path, client)

    assert not saved["raw_response_receipts_complete"]
    assert "compilation-scoped" in saved["raw_response_receipts_incomplete_reason"]
    assert saved["raw_responses"] == []


def test_scoped_receipts_isolate_reused_client_and_repeated_cached_urls(tmp_path):
    client = CachedClient(cache_dir=str(tmp_path))
    old_url = "https://opendata.smhi.se/old"
    shared_url = "https://opendata.smhi.se/shared"
    Path(client._cache_path(old_url, "json")).write_text('{"old":true}')
    Path(client._cache_path(shared_url, "json")).write_text('{"value":42}')
    client.get_json(old_url)

    first = client.scoped()
    second = client.scoped()
    first.get_json(shared_url)
    first.get_json(shared_url)
    second.get_json(shared_url)

    for label, scope in [("first", first), ("second", second)]:
        saved = _save_receipt(tmp_path, scope, label)
        assert saved["raw_response_receipts_complete"]
        assert saved["raw_response_receipts_incomplete_reason"] is None
        assert [receipt["url"] for receipt in saved["raw_responses"]] == [shared_url]
    assert [receipt["url"] for receipt in client.response_receipts.values()] == [
        old_url
    ]
    assert first.session is client.session is second.session
    assert first._receipt_lock is not second._receipt_lock


def test_scoped_receipts_fingerprint_changed_payloads_without_erasing_history(tmp_path):
    client = CachedClient(cache_dir=str(tmp_path))
    url = "https://opendata.smhi.se/changing"
    cached = Path(client._cache_path(url, "json"))
    first = client.scoped()
    second = client.scoped()
    cached.write_text('{"value":1}', encoding="utf-8")
    first.get_json(url)
    cached.write_text('{"value":2}', encoding="utf-8")
    first.get_json(url)
    second.get_json(url)

    first_saved = _save_receipt(tmp_path, first, "first")
    second_saved = _save_receipt(tmp_path, second, "second")
    assert len(first_saved["raw_responses"]) == 2
    assert len(second_saved["raw_responses"]) == 1
    assert (
        second_saved["raw_responses"][0]["sha256"]
        == hashlib.sha256(b'{"value":2}').hexdigest()
    )


def test_simultaneous_scope_reads_have_independent_receipts(tmp_path):
    client = CachedClient(cache_dir=str(tmp_path))
    urls = [f"https://opendata.smhi.se/scope/{number}" for number in range(2)]
    scopes = [client.scoped(), client.scoped()]
    for number, url in enumerate(urls):
        Path(client._cache_path(url, "json")).write_text(
            json.dumps({"scope": number}), encoding="utf-8"
        )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda item: item[0].get_json(item[1]), zip(scopes, urls))
        )

    assert results == [{"scope": 0}, {"scope": 1}]
    for number, scope in enumerate(scopes):
        saved = _save_receipt(tmp_path, scope, f"scope-{number}")
        assert [receipt["url"] for receipt in saved["raw_responses"]] == [urls[number]]
    assert client.response_receipts == {}


def test_compilations_reusing_client_record_their_own_repeated_requests(tmp_path):
    client = _RecordingFakeClient()
    old_url = "https://previous.example/unrelated"
    client._record_response(old_url, "txt", "old parser input", cached=False)
    saved_receipts = []

    for label in ["first", "second"]:
        output = tmp_path / f"{label}.epw"
        receipt = tmp_path / f"{label}.json"
        config = EPWConfig(
            year=YEAR,
            output_path=str(output),
            station_id=STATION_ID,
            provenance_path=str(receipt),
            weather_policy="strict",
        )
        compile_epw(config, client=client)
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        assert saved["raw_response_receipts_complete"]
        assert saved["raw_responses"]
        assert old_url not in {entry["url"] for entry in saved["raw_responses"]}
        saved_receipts.append(saved["raw_responses"])

    assert saved_receipts[0] == saved_receipts[1]
    assert [entry["url"] for entry in client.response_receipts.values()] == [old_url]


def test_provenance_is_saved_as_utf8_json(tmp_path):
    _save_receipt(tmp_path, FakeClient())
    encoded = (tmp_path / "weather.json").read_bytes()

    assert "Göteborg".encode("utf-8") in encoded
    assert json.loads(encoded)["configuration"]["city"] == "Göteborg"


def test_sidecar_replacement_failure_preserves_epw_and_existing_receipt(
    tmp_path, monkeypatch
):
    receipt = tmp_path / "weather.json"
    receipt.write_text("existing receipt", encoding="utf-8")
    original_paths = set(tmp_path.iterdir())

    def fail_replacement(source, target):
        raise OSError("simulated sidecar replacement failure")

    monkeypatch.setattr("smhi2epw.provenance.os.replace", fail_replacement)
    with pytest.raises(OSError, match="simulated sidecar"):
        _save_receipt(tmp_path, FakeClient())

    assert receipt.read_text(encoding="utf-8") == "existing receipt"
    assert (tmp_path / "weather.epw").read_text(encoding="utf-8") == (
        "EPW artifact preserved independently"
    )
    assert set(tmp_path.iterdir()) == original_paths | {tmp_path / "weather.epw"}


def test_sidecar_serialization_failure_preserves_existing_artifacts(tmp_path):
    output = tmp_path / "weather.epw"
    receipt = tmp_path / "weather.json"
    output.write_text("existing EPW", encoding="utf-8")
    receipt.write_text("existing receipt", encoding="utf-8")
    config = EPWConfig(YEAR, str(output), provenance_path=str(receipt))
    result = _ReceiptResult(str(output), rows=float("nan"))

    with pytest.raises(ValueError, match="JSON compliant"):
        write_provenance(config, result, FakeClient())

    assert output.read_text(encoding="utf-8") == "existing EPW"
    assert receipt.read_text(encoding="utf-8") == "existing receipt"
    assert set(tmp_path.iterdir()) == {output, receipt}

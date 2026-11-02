#!/usr/bin/env python3
"""Wait for this run's bounded, non-secret encrypted-APK receipt on GitHub.

Only the fixed repository/path is read.  The workflow's contents-read GH_TOKEN
never enters the receipt, command output, or a redirected request.  The checked
out runner code stays pinned even while this separate receipt branch advances.
"""
import argparse
import base64
import binascii
import http.client
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


REPOSITORY = "constantinepetrov/android"
RECEIPT_PATH = "qa/relay-receipt.json"
DEFAULT_BRANCH = "codex/kam-cloud-qa"
APK_BYTES = 856629249
MAX_RESPONSE_BYTES = 64 * 1024
POLL_SECONDS = 10
REQUEST_TIMEOUT = 20
MAX_TIMEOUT = 900
SAFE_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
RUN_NUMBER = re.compile(r"[1-9][0-9]{0,19}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT_FIELDS = frozenset((
    "schema_version", "request_id", "github_run_id", "github_run_attempt",
    "artifact_name", "zip_bytes", "zip_sha256",
))


class ReceiptError(Exception):
    """Invalid input or a non-transient API failure; do not expose internals."""


class ReceiptTimeout(ReceiptError):
    """The overall bounded wait has expired."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # This small Contents request has no reason to transfer its token to
        # another endpoint.  A 3xx becomes a closed, generic failure.
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError()
        result[key] = value
    return result


def _invalid_constant(value):
    raise ReceiptError()


def _json(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_RESPONSE_BYTES:
        raise ReceiptError()
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReceiptError() from None


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def valid_branch(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", value):
        return False
    return (".." not in value and "//" not in value
            and not value.endswith((".", "/"))
            and all(not part.startswith(".") and not part.endswith(".lock")
                    for part in value.split("/")))


def decode_receipt(response, request_id, run_id, run_attempt):
    """Return a validated matching receipt, or None for a valid different run."""
    envelope = _json(response)
    if (not isinstance(envelope, dict)
            or envelope.get("type") != "file"
            or envelope.get("encoding") != "base64"
            or envelope.get("name") != "relay-receipt.json"
            or envelope.get("path") != RECEIPT_PATH
            or envelope.get("submodule_git_url") is not None):
        raise ReceiptError()
    encoded = envelope.get("content")
    size = envelope.get("size")
    if (not isinstance(encoded, str) or len(encoded) > MAX_RESPONSE_BYTES
            or type(size) is not int or not 0 < size <= MAX_RESPONSE_BYTES):
        raise ReceiptError()
    try:
        content = base64.b64decode(encoded.replace("\n", "").replace("\r", ""), validate=True)
    except (ValueError, binascii.Error):
        raise ReceiptError() from None
    if len(content) != size:
        raise ReceiptError()
    receipt = _json(content)
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise ReceiptError()
    if (type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or not _matches(SAFE_REQUEST, receipt["request_id"])
            or not _matches(RUN_NUMBER, receipt["github_run_id"])
            or not _matches(RUN_NUMBER, receipt["github_run_attempt"])
            or not _matches(SHA256, receipt["zip_sha256"])
            or type(receipt["zip_bytes"]) is not int
            or not APK_BYTES < receipt["zip_bytes"] < APK_BYTES + 1024 * 1024):
        raise ReceiptError()
    expected_name = "kam-encrypted-apk-" + receipt["github_run_id"] + "-" + receipt["github_run_attempt"]
    if receipt["artifact_name"] != expected_name:
        raise ReceiptError()
    # Validate the entire stale object before deciding to wait.  A run retry
    # has its own identity, so a previous attempt must not be accepted either.
    if (receipt["github_run_id"], receipt["github_run_attempt"]) != (run_id, run_attempt):
        return None
    if receipt["request_id"] != request_id:
        raise ReceiptError()
    return receipt


def fetch_contents(opener, token, branch, remaining):
    """Read at most 64 KiB; absent/transient responses are retried by the caller."""
    if remaining <= 0:
        raise ReceiptTimeout()
    url = ("https://api.github.com/repos/" + REPOSITORY + "/contents/" + RECEIPT_PATH
           + "?" + urllib.parse.urlencode({"ref": branch}))
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Accept-Encoding": "identity",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "KaMCloudQA-Receipt/1.0",
        "Cache-Control": "no-cache",
    })
    try:
        with opener.open(request, timeout=min(REQUEST_TIMEOUT, remaining)) as response:
            if response.status != 200:
                raise ReceiptError()
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ReceiptError()
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if not 0 < int(length) <= MAX_RESPONSE_BYTES:
                        raise ReceiptError()
                except ValueError:
                    raise ReceiptError() from None
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if not 0 < len(data) <= MAX_RESPONSE_BYTES:
                raise ReceiptError()
            return data
    except urllib.error.HTTPError as exc:
        # Do not read error bodies or include exception/request strings in logs.
        code = exc.code
        exc.close()
        if code == 404 or code in (408, 429, 500, 502, 503, 504):
            return None
        # All 403s fail closed, including permission errors and ambiguous limits.
        raise ReceiptError() from None
    except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, OSError):
        return None


def save_receipt(output, receipt):
    """Publish one complete private JSON file using a same-directory rename."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".relay-receipt-", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def wait_for_receipt(request_id, output, timeout, branch, token, run_id, run_attempt):
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(NoRedirect())
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReceiptTimeout()
        raw = fetch_contents(opener, token, branch, remaining)
        if time.monotonic() >= deadline:
            raise ReceiptTimeout()
        if raw is not None:
            receipt = decode_receipt(raw, request_id, run_id, run_attempt)
            if receipt is not None:
                save_receipt(output, receipt)
                return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReceiptTimeout()
        time.sleep(min(POLL_SECONDS, remaining))


def _alarm(signum, frame):
    # A socket timeout alone is insufficient against a slowly trickled body.
    raise ReceiptTimeout()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    args = parser.parse_args(argv)
    if not _matches(SAFE_REQUEST, args.request_id):
        parser.error("request id must be a bounded safe identifier")
    if not valid_branch(args.branch):
        parser.error("branch must be a bounded safe ref")
    if not 1 <= args.timeout <= MAX_TIMEOUT:
        parser.error("timeout must be between 1 and 900 seconds")

    old_handler = None
    try:
        token = os.environ.get("GH_TOKEN", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or not token
                or not _matches(RUN_NUMBER, run_id) or not _matches(RUN_NUMBER, run_attempt)):
            raise ReceiptError()
        # This script is for the Linux/macOS Actions runner.  A wall-time alarm
        # bounds DNS, connection, response reads, retries and final persistence.
        old_handler = signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, args.timeout)
        wait_for_receipt(args.request_id, args.output, args.timeout, args.branch,
                         token, run_id, run_attempt)
    except ReceiptTimeout:
        print("relay receipt timed out", file=sys.stderr)
        return 1
    except Exception:
        print("relay receipt unavailable or invalid", file=sys.stderr)
        return 1
    finally:
        if old_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    print("matching receipt received", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

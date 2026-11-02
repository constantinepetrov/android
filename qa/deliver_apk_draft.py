#!/usr/bin/env python3
"""Deliver one exact existing APK as an unpublished GitHub release asset.

No endpoint in this script can publish, update, or delete a release or asset.
Only a fresh, explicitly requested draft is created. Failed writes are reconciled
by one read before stopping; they are never blindly retried.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


REPOSITORY = "constantinepetrov/android"
BRANCH = "codex/kam-cloud-qa"
MASTER_SHA = "11cd5fd0e10ae6e8cfce27493564e49cd8ee11d5"
APK_BYTES = 856629249
APK_SHA256 = "c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4"
ASSET_NAME = "KaM_Remake_ARM64_with_data.apk"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY
MAX_JSON = 2 * 1024 * 1024
REQUEST_FIELDS = {
    "schema_version", "request_id", "action", "draft", "tag_name",
    "target_commitish", "apk_bytes", "apk_sha256",
}


class DeliveryError(Exception):
    """A safe, fixed diagnostic code, never a URL or credential."""


def require(condition, code):
    if not condition:
        raise DeliveryError(code)


def validate_request(value):
    require(isinstance(value, dict) and set(value) == REQUEST_FIELDS, "REQUEST_FIELDS")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1,
            "REQUEST_VERSION")
    require(value["action"] == "upload-existing-apk-to-draft-release"
            and value["draft"] is True, "DRAFT_ONLY")
    require(isinstance(value["request_id"], str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", value["request_id"]),
            "REQUEST_ID")
    require(isinstance(value["tag_name"], str)
            and re.fullmatch(r"kam-apk-delivery-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value["tag_name"])
            and ".." not in value["tag_name"] and not value["tag_name"].endswith("."), "TAG_NAME")
    require(value["target_commitish"] == MASTER_SHA, "RELEASE_TARGET")
    require(type(value["apk_bytes"]) is int and value["apk_bytes"] == APK_BYTES
            and value["apk_sha256"] == APK_SHA256, "APK_IDENTITY")
    return value


def load_request(file):
    require(file.is_file() and file.stat().st_size <= 4096, "REQUEST_FILE")
    return validate_request(json.loads(file.read_text()))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token):
        require(bool(token), "MISSING_TOKEN")
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def json(self, path, method="GET", value=None, file=None):
        if file is not None:
            require(method == "POST" and path.startswith("https://uploads.github.com/repos/"
                    + REPOSITORY + "/releases/"), "UPLOAD_ENDPOINT")
            url, data, content_type = path, file, "application/vnd.android.package-archive"
            length = APK_BYTES
        else:
            require(path.startswith("/") and not path.startswith("//"), "API_PATH")
            url = API_ROOT + path
            data = None if value is None else json.dumps(value).encode()
            content_type = "application/json"
            length = None if data is None else len(data)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "KaM-Private-APK-Delivery/1.0",
            "Content-Type": content_type,
        }
        if length is not None:
            headers["Content-Length"] = str(length)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120) as response:
                require(response.status == (201 if method == "POST" else 200), "API_STATUS")
                body = response.read(MAX_JSON + 1)
                require(len(body) <= MAX_JSON, "API_RESPONSE_SIZE")
                return json.loads(body)
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            raise DeliveryError("HTTP_" + str(code)) from None
        except (OSError, ValueError, http.client.HTTPException, urllib.error.URLError):
            raise DeliveryError("API_IO_OR_JSON") from None


def release_body(request, run_id, attempt):
    return (
        "Private delivery of the existing KaM Remake ARM64 APK with bundled game data.\n\n"
        "This is an unpublished draft for the repository owner/collaborators. "
        "The APK has not been rebuilt or changed.\n\n"
        f"File: {ASSET_NAME}\nSize: {APK_BYTES} bytes\nSHA-256: {APK_SHA256}\n\n"
        "The cloud test reached Battle Tutorial, moved units and verified save/load. "
        "It does not establish physical-device performance or audible audio.\n"
        "QA report: https://github.com/constantinepetrov/android/blob/"
        "cecfdad6fd9f02a5998f5bcdc29d915b749ca4e6/qa/CLOUD_QA.md\n\n"
        "The draft target points to the unchanged master commit only as a delivery "
        "container. It is not the source revision of a newly built APK.\n\n"
        f"<!-- kam-apk-delivery request={request['request_id']} run={run_id} attempt={attempt} -->"
    )


def validate_release(release, request, body):
    require(isinstance(release, dict) and type(release.get("id")) is int
            and release["id"] > 0, "RELEASE_ID")
    require(release.get("draft") is True and release.get("published_at") is None,
            "REMOTE_NOT_DRAFT")
    require(release.get("tag_name") == request["tag_name"]
            and release.get("target_commitish") == MASTER_SHA
            and release.get("name") == "KaM Android — private APK download"
            and release.get("body") == body, "RELEASE_IDENTITY")
    expected = f"https://uploads.github.com/repos/{REPOSITORY}/releases/{release['id']}/assets"
    require(release.get("upload_url") == expected + "{?name,label}", "UPLOAD_URL")
    return release


def validate_asset(asset):
    require(isinstance(asset, dict) and type(asset.get("id")) is int
            and asset["id"] > 0, "ASSET_ID")
    require(asset.get("name") == ASSET_NAME and asset.get("state") == "uploaded",
            "ASSET_STATE")
    require(type(asset.get("size")) is int and asset["size"] == APK_BYTES
            and asset.get("digest") == "sha256:" + APK_SHA256, "REMOTE_APK_IDENTITY")
    url = asset.get("browser_download_url", "")
    require(isinstance(url, str) and url.startswith(f"https://github.com/{REPOSITORY}/releases/download/")
            and url.endswith("/" + ASSET_NAME) and "?" not in url and "#" not in url,
            "ASSET_DOWNLOAD_URL")
    return asset


def find_release(api, tag):
    # Bounded pagination includes drafts under the runner's write-capable token.
    for page in range(1, 11):
        releases = api.json(f"/releases?per_page=100&page={page}")
        require(isinstance(releases, list), "RELEASE_LIST")
        matches = [item for item in releases if item.get("tag_name") == tag]
        require(len(matches) <= 1, "DUPLICATE_RELEASE")
        if matches:
            return matches[0]
        if len(releases) < 100:
            return None
    raise DeliveryError("RELEASE_LIST_LIMIT")


def deliver(api, request, apk, run_id, attempt):
    with apk.open("rb") as source:
        require(apk.stat().st_size == APK_BYTES
                and hashlib.file_digest(source, "sha256").hexdigest() == APK_SHA256,
                "LOCAL_APK_IDENTITY")
    target = api.json("/git/ref/heads/master")
    require(target.get("object", {}).get("sha") == MASTER_SHA, "MASTER_MOVED")
    require(find_release(api, request["tag_name"]) is None, "RELEASE_ALREADY_EXISTS")
    try:
        api.json("/git/ref/tags/" + urllib.parse.quote(request["tag_name"], safe=""))
    except DeliveryError as error:
        require(str(error) == "HTTP_404", "TAG_CHECK_FAILED")
    else:
        raise DeliveryError("TAG_ALREADY_EXISTS")
    body = release_body(request, run_id, attempt)
    payload = {
        "tag_name": request["tag_name"], "target_commitish": MASTER_SHA,
        "name": "KaM Android — private APK download", "body": body,
        "draft": True, "prerelease": True, "make_latest": "false",
        "generate_release_notes": False,
    }
    try:
        release = api.json("/releases", "POST", value=payload)
    except DeliveryError:
        # The POST may have succeeded while its response was lost. Inspect once;
        # never create a second release or reuse any other request's draft.
        release = find_release(api, request["tag_name"])
        require(release is not None, "CREATE_UNCONFIRMED")
    validate_release(release, request, body)
    release_path = "/releases/" + str(release["id"])
    release = validate_release(api.json(release_path), request, body)
    require(release.get("assets") == [], "DRAFT_HAS_ASSETS")
    upload_url = release["upload_url"].removesuffix("{?name,label}")
    upload_url += "?" + urllib.parse.urlencode({"name": ASSET_NAME})
    try:
        with apk.open("rb") as source:
            api.json(upload_url, "POST", file=source)
    except DeliveryError:
        # A failed upload response is ambiguous. The single read below decides
        # whether the exact completed asset exists; no overwrite or retry.
        pass
    release = validate_release(api.json(release_path), request, body)
    assets = release.get("assets")
    require(isinstance(assets, list) and len(assets) == 1, "ASSET_UPLOAD_UNCONFIRMED")
    asset = validate_asset(assets[0])
    asset_readback = validate_asset(api.json("/releases/assets/" + str(asset["id"])))
    require(asset_readback["id"] == asset["id"], "ASSET_READBACK_ID")
    release_url = release.get("html_url", "")
    require(isinstance(release_url, str)
            and release_url.startswith(f"https://github.com/{REPOSITORY}/releases/")
            and "?" not in release_url and "#" not in release_url, "RELEASE_URL")
    return {
        "schema_version": 1, "status": "DELIVERED_AS_DRAFT_RELEASE",
        "request_id": request["request_id"], "github_run_id": run_id,
        "github_run_attempt": attempt, "release_id": release["id"],
        "release_url": release_url, "tag_name": request["tag_name"], "draft": True,
        "target_commitish": MASTER_SHA, "asset_id": asset["id"],
        "asset_name": ASSET_NAME, "asset_state": asset["state"],
        "apk_bytes": APK_BYTES, "apk_sha256": APK_SHA256,
        "remote_digest": asset["digest"],
        "download_url": asset_readback["browser_download_url"], "rebuilt": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--validate-request", action="store_true")
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        request = load_request(args.request)
        if args.validate_request:
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write("request-id=" + request["request_id"] + "\n")
            print(json.dumps({"status": "DRAFT_DELIVERY_REQUEST_VALID", "request_id": request["request_id"]}))
            return 0
        require(args.apk is not None and args.evidence is not None, "MISSING_PATHS")
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
                and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "RUN_CONTEXT")
        run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
        require(re.fullmatch(r"[1-9][0-9]*", run_id)
                and re.fullmatch(r"[1-9][0-9]*", attempt), "RUN_IDENTITY")
        receipt = deliver(GitHub(os.environ.get("GH_TOKEN", "")), request, args.apk, run_id, attempt)
        args.evidence.mkdir(parents=True, exist_ok=True)
        (args.evidence / "delivery.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt))
        return 0
    except DeliveryError as error:
        print("APK delivery stopped: " + str(error), file=sys.stderr)
    except Exception:
        # Never expose request headers, token-bearing objects, or response URLs.
        print("APK delivery stopped: LOCAL_OR_RESPONSE_ERROR", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

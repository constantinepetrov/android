# Deliver the existing APK as one private draft asset

The user requested one complete installable APK. The connected chat and Google
Drive upload paths rejected the 856,629,249-byte file before upload because their
transfer ceiling is 536,870,912 bytes. That ceiling belongs to those transfer
paths, not to Google Drive storage.

`kam-apk-delivery.yml` reuses the verified encrypted input relay, then attaches
the original APK to a **draft** GitHub release. It does not rebuild the app or run
Android. The release remains unpublished and requires repository write access
to view; the owner should sign in to `constantinepetrov` before downloading.

## File identity

- Filename: `KaM_Remake_ARM64_with_data.apk`
- Bytes: `856629249`
- SHA-256: `c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4`
- Bundled package label: `1.0-r16397`; native engine identifies as `r16398`.

The draft is a delivery container for the pre-existing APK. Its target commit is
the unchanged default-branch revision because the workflow token cannot create
a release targeting a commit with different workflow files. The release notes
identify the APK by its hash and refer to the actual QA evidence separately.

## Scope and evidence

Only a change to `qa/delivery-request.json` on `codex/kam-cloud-qa` starts delivery.
The workflow shares the existing QA concurrency group, since both consumers use
the same run-bound `qa/relay-receipt.json` path. The relay keeps its existing
request, run, attempt, ciphertext digest and plaintext APK identity checks.

The delivery step requires the remote release to remain a draft and the remote
asset's completed state, size and SHA-256 to match the local file. Only the small
delivery receipt is retained as a workflow artifact. The APK is never placed in
Git or an ordinary public workflow artifact. Temporary encrypted input and
handshake artifacts are removed by the existing scoped cleanup procedure.

Downloading this file does not extend the QA claims in [CLOUD_QA.md](CLOUD_QA.md).
The prior checks demonstrated startup, Battle Tutorial control, advancing game
ticks and a save/load round trip on the cloud emulator. Audible audio and a
physical phone remain untested.

## Service references

- [GitHub release assets must be under 2 GiB](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
- [Draft visibility and workflow-token permissions](https://docs.github.com/en/rest/releases/releases).
- [Google Drive file size limits](https://support.google.com/drive/answer/37603?hl=en).

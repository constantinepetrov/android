'use strict';

// Use only the one-blob capability returned by this QA run. No GitHub token is
// read or transmitted. Do not log SDK error objects: they can contain SAS URLs.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { BlockBlobClient } = require('@azure/storage-blob');

async function main() {
  const [capsulePath, zipPath, receiptPath] = process.argv.slice(2);
  if (!capsulePath || !zipPath || !receiptPath) throw new Error('arguments');
  const capsule = JSON.parse(fs.readFileSync(capsulePath, 'utf8'));
  const receipt = JSON.parse(fs.readFileSync(receiptPath, 'utf8'));
  for (const key of ['request_id', 'github_run_id', 'github_run_attempt', 'artifact_name']) {
    if (capsule[key] !== receipt[key]) throw new Error('identity');
  }
  const size = fs.statSync(zipPath).size;
  const hash = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(zipPath)) hash.update(chunk);
  if (size !== receipt.zip_bytes || hash.digest('hex') !== receipt.zip_sha256) throw new Error('zip hash');
  const url = new URL(capsule.signed_upload_url);
  if (url.protocol !== 'https:' || !url.hostname.endsWith('.blob.core.windows.net') || url.username || url.password) {
    throw new Error('upload host');
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8 * 60 * 1000);
  let uploaded = 0;
  try {
    const client = new BlockBlobClient(capsule.signed_upload_url);
    const response = await client.uploadFile(zipPath, {
      blockSize: 8 * 1024 * 1024, concurrency: 4,
      blobHTTPHeaders: { blobContentType: 'application/zip' },
      abortSignal: controller.signal,
      onProgress: ({loadedBytes}) => {
        if (loadedBytes - uploaded >= 128 * 1024 * 1024 || loadedBytes === size) {
          uploaded = loadedBytes;
          process.stdout.write(JSON.stringify({status:'UPLOADING_ENCRYPTED_APK',bytes:loadedBytes,total:size}) + '\n');
        }
      },
    });
    if (!response.etag) throw new Error('unconfirmed upload');
    fs.writeFileSync(receiptPath + '.uploaded', JSON.stringify({
      uploaded:true, run_id:receipt.github_run_id, zip_bytes:size, zip_sha256:receipt.zip_sha256,
    }) + '\n', {flag:'wx', mode:0o600});
    process.stdout.write(JSON.stringify({status:'ENCRYPTED_APK_UPLOADED',run_id:receipt.github_run_id,bytes:size}) + '\n');
  } finally { clearTimeout(timer); }
}
main().catch(() => { process.stderr.write('Encrypted artifact upload failed; no receipt should be published.\n'); process.exitCode = 1; });

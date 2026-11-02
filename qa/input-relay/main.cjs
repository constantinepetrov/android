'use strict';

// Internal protocol is deliberately pinned to @actions/artifact 6.3.1.
// Its own upload-artifact.js uses CreateArtifact version 7 and the same
// CreateArtifact -> Azure signed blob upload -> FinalizeArtifact sequence.
// Only the single-blob SAS URL leaves this job, inside an encrypted capsule.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {pathToFileURL} = require('node:url');
const {Transform} = require('node:stream');
const {pipeline} = require('node:stream/promises');

const SDK_VERSION = '6.3.1';
const PROTOCOL_VERSION = 7;
const APK_BYTES = 856629249;
const APK_SHA256 = 'c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4';
const TRANSPORT_AAD = Buffer.from('kam-input-relay-transport-v1', 'ascii');
const SAFE_CODE = /^KAM_RELAY_[A-Z0-9_]+$/;

class RelayError extends Error {
  constructor(code) { super(code); this.code = code; }
}
function need(condition, code) { if (!condition) throw new RelayError(code); }
function readJson(file, maxBytes = 16384) {
  const info = fs.lstatSync(file);
  need(info.isFile() && info.size > 0 && info.size <= maxBytes, 'KAM_RELAY_JSON_FILE');
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  need(value && typeof value === 'object' && !Array.isArray(value), 'KAM_RELAY_JSON_OBJECT');
  return value;
}
function writePrivate(file, value, exclusive = true) {
  const body = JSON.stringify(value, null, 2) + '\n';
  fs.writeFileSync(file, body, {encoding: 'utf8', mode: 0o600, flag: exclusive ? 'wx' : 'w'});
  fs.chmodSync(file, 0o600);
}
function replacePrivate(file, value) {
  const temporary = file + '.new';
  writePrivate(temporary, value);
  fs.renameSync(temporary, file);
}
function decodeKey(value, size) {
  need(typeof value === 'string' && /^[A-Za-z0-9+/]+={0,2}$/.test(value), 'KAM_RELAY_KEY_FORMAT');
  const decoded = Buffer.from(value, 'base64');
  need(decoded.length === size && decoded.toString('base64') === value, 'KAM_RELAY_KEY_LENGTH');
  return decoded;
}
function runtimeContext(requestId) {
  const run = process.env.GITHUB_RUN_ID || '';
  const attempt = process.env.GITHUB_RUN_ATTEMPT || '';
  const temp = process.env.RUNNER_TEMP || '';
  need(/^[1-9][0-9]*$/.test(run) && /^[1-9][0-9]*$/.test(attempt), 'KAM_RELAY_RUN_CONTEXT');
  need(/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,159}$/.test(requestId), 'KAM_RELAY_REQUEST_ID');
  need(path.isAbsolute(temp), 'KAM_RELAY_TEMP_PATH');
  return {
    schema_version: 1, request_id: requestId, github_run_id: run,
    github_run_attempt: attempt, artifact_name: `kam-encrypted-apk-${run}-${attempt}`,
    state_path: path.join(temp, 'kam-relay-state.json'),
    handshake_directory: path.join(temp, 'kam-relay-handshake')
  };
}
function assertIdentity(value, context) {
  for (const key of ['schema_version', 'request_id', 'github_run_id', 'github_run_attempt', 'artifact_name']) {
    need(value[key] === context[key], 'KAM_RELAY_IDENTITY_MISMATCH');
  }
}
function readState(context, status) {
  const state = readJson(context.state_path);
  assertIdentity(state, context);
  need((fs.statSync(context.state_path).mode & 0o077) === 0, 'KAM_RELAY_STATE_PERMISSIONS');
  need(state.status === status, 'KAM_RELAY_STATE_STATUS');
  need(state.expected_apk?.bytes === APK_BYTES && state.expected_apk?.sha256 === APK_SHA256,
    'KAM_RELAY_STATE_APK_IDENTITY');
  return state;
}
function validateReceipt(receipt, context) {
  const expectedKeys = ['schema_version', 'request_id', 'github_run_id', 'github_run_attempt',
    'artifact_name', 'zip_bytes', 'zip_sha256'].sort();
  need(JSON.stringify(Object.keys(receipt).sort()) === JSON.stringify(expectedKeys), 'KAM_RELAY_RECEIPT_FIELDS');
  assertIdentity(receipt, context);
  // Ciphertext is APK_BYTES + a 16-byte GCM tag. ZIP may only add bounded framing.
  need(Number.isSafeInteger(receipt.zip_bytes) && receipt.zip_bytes > APK_BYTES + 16 &&
    receipt.zip_bytes <= APK_BYTES + 1024 * 1024, 'KAM_RELAY_RECEIPT_SIZE');
  need(typeof receipt.zip_sha256 === 'string' && /^[0-9a-f]{64}$/.test(receipt.zip_sha256),
    'KAM_RELAY_RECEIPT_HASH');
  return receipt;
}

async function loadSdk() {
  // Absolute imports deliberately bypass the package's public-only exports map.
  // Every imported file belongs to the exact package checked below and npm lock.
  const root = path.join(__dirname, 'node_modules', '@actions', 'artifact');
  need(readJson(path.join(root, 'package.json')).version === SDK_VERSION, 'KAM_RELAY_SDK_VERSION');
  const moduleAt = relative => import(pathToFileURL(path.join(root, 'lib', relative)).href);
  const [client, util, generated, retention] = await Promise.all([
    moduleAt('internal/shared/artifact-twirp-client.js'),
    moduleAt('internal/shared/util.js'), moduleAt('generated/index.js'),
    moduleAt('internal/upload/retention.js')
  ]);
  return {
    client: client.internalArtifactTwirpClient(),
    backendIds: util.getBackendIdsFromToken(),
    StringValue: generated.StringValue, expiresAt: retention.getExpiration(1)
  };
}

function encryptCapsule(capsule, publicKey) {
  const key = crypto.randomBytes(32);
  const iv = crypto.randomBytes(12);
  try {
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    cipher.setAAD(TRANSPORT_AAD);
    const ciphertext = Buffer.concat([cipher.update(Buffer.from(JSON.stringify(capsule), 'utf8')), cipher.final()]);
    const wrapped = crypto.publicEncrypt({key: publicKey, padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: 'sha256'}, key);
    return {
      schema_version: 1, algorithm: 'RSA-OAEP-SHA256+A256GCM',
      key_fingerprint_sha256: crypto.createHash('sha256').update(publicKey.export({type: 'spki', format: 'der'})).digest('hex'),
      wrapped_key_b64: wrapped.toString('base64'), iv_b64: iv.toString('base64'),
      tag_b64: cipher.getAuthTag().toString('base64'), ciphertext_b64: ciphertext.toString('base64')
    };
  } finally { key.fill(0); }
}

async function prepare(context, core) {
  need(!fs.existsSync(context.state_path) && !fs.existsSync(context.handshake_directory), 'KAM_RELAY_ALREADY_PREPARED');
  const publicKey = crypto.createPublicKey(fs.readFileSync(path.join(__dirname, 'transport-public.pem')));
  need(publicKey.asymmetricKeyType === 'rsa' && publicKey.asymmetricKeyDetails.modulusLength >= 2048,
    'KAM_RELAY_PUBLIC_KEY');
  const sdk = await loadSdk();
  let created;
  try {
    created = await sdk.client.CreateArtifact({
      ...sdk.backendIds, name: context.artifact_name,
      mimeType: sdk.StringValue.create({value: 'application/zip'}),
      version: PROTOCOL_VERSION, expiresAt: sdk.expiresAt
    });
  } catch { throw new RelayError('KAM_RELAY_CREATE_FAILED'); }
  need(created?.ok && typeof created.signedUploadUrl === 'string', 'KAM_RELAY_CREATE_RESPONSE');
  core.setSecret(created.signedUploadUrl);
  const uploadUrl = new URL(created.signedUploadUrl);
  need(uploadUrl.protocol === 'https:' && !uploadUrl.username && !uploadUrl.password &&
    uploadUrl.searchParams.has('sig'), 'KAM_RELAY_UPLOAD_URL');
  const payloadKey = crypto.randomBytes(32);
  const payloadNonce = crypto.randomBytes(12);
  try {
    const identity = {schema_version: 1, request_id: context.request_id, github_run_id: context.github_run_id,
      github_run_attempt: context.github_run_attempt, artifact_name: context.artifact_name};
    const payloadCipher = {algorithm: 'AES-256-GCM', key_b64: payloadKey.toString('base64'),
      nonce_b64: payloadNonce.toString('base64')};
    core.setSecret(payloadCipher.key_b64);
    core.setSecret(payloadCipher.nonce_b64);
    const expectedApk = {bytes: APK_BYTES, sha256: APK_SHA256};
    const capsule = {...identity, signed_upload_url: created.signedUploadUrl,
      payload_cipher: payloadCipher, expected_apk: expectedApk};
    const envelope = encryptCapsule(capsule, publicKey);
    writePrivate(context.state_path, {...identity, status: 'PREPARED', backend_ids: sdk.backendIds,
      payload_cipher: payloadCipher, expected_apk: expectedApk, created_at: new Date().toISOString()});
    fs.mkdirSync(context.handshake_directory, {mode: 0o700});
    writePrivate(path.join(context.handshake_directory, 'transport.json'), envelope);
    writePrivate(path.join(context.handshake_directory, 'metadata.json'), {
      ...identity, expected_apk: expectedApk, key_fingerprint_sha256: envelope.key_fingerprint_sha256,
      transport_algorithm: envelope.algorithm, payload_filename: 'app.apk.enc',
      payload_format: 'AES-256-GCM ciphertext followed by 16-byte tag; no AAD'
    });
    core.setOutput('handshake-directory', context.handshake_directory);
    core.setOutput('artifact-name', context.artifact_name);
    core.info('Prepared an encrypted transport capsule for one pinned APK.');
  } finally { payloadKey.fill(0); payloadNonce.fill(0); }
}

async function finalize(context, core) {
  const state = readState(context, 'PREPARED');
  const receipt = validateReceipt(readJson(core.getInput('receipt-path', {required: true}), 4096), context);
  const sdk = await loadSdk();
  need(sdk.backendIds.workflowRunBackendId === state.backend_ids?.workflowRunBackendId &&
    sdk.backendIds.workflowJobRunBackendId === state.backend_ids?.workflowJobRunBackendId,
    'KAM_RELAY_DIFFERENT_JOB');
  let result;
  try {
    result = await sdk.client.FinalizeArtifact({...state.backend_ids, name: context.artifact_name,
      size: String(receipt.zip_bytes), hash: sdk.StringValue.create({value: `sha256:${receipt.zip_sha256}`})});
  } catch { throw new RelayError('KAM_RELAY_FINALIZE_FAILED'); }
  need(result?.ok && /^[1-9][0-9]*$/.test(String(result.artifactId)), 'KAM_RELAY_FINALIZE_RESPONSE');
  state.status = 'FINALIZED';
  state.artifact_id = String(result.artifactId);
  state.receipt = receipt;
  replacePrivate(context.state_path, state);
  core.setOutput('artifact-id', state.artifact_id);
  core.setOutput('artifact-name', context.artifact_name);
  core.info('Finalized the encrypted input artifact; APK verification is still pending.');
}

async function decryptVerified(input, output, key, nonce, expected) {
  const info = fs.lstatSync(input);
  need(info.isFile() && info.size === expected.bytes + 16, 'KAM_RELAY_CIPHERTEXT_SIZE');
  need(path.resolve(input) !== path.resolve(output) && !fs.existsSync(output), 'KAM_RELAY_APK_OUTPUT_EXISTS');
  fs.mkdirSync(path.dirname(output), {recursive: true, mode: 0o700});
  const partial = output + '.part';
  need(!fs.existsSync(partial), 'KAM_RELAY_PARTIAL_EXISTS');
  const handle = await fs.promises.open(input, 'r');
  let ownsPartial = false;
  try {
    const tag = Buffer.alloc(16);
    const read = await handle.read(tag, 0, 16, expected.bytes);
    need(read.bytesRead === 16, 'KAM_RELAY_CIPHERTEXT_TAG');
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, nonce);
    decipher.setAuthTag(tag);
    let bytes = 0;
    const sha256 = crypto.createHash('sha256');
    const counter = new Transform({transform(chunk, encoding, callback) {
      bytes += chunk.length;
      if (bytes > expected.bytes) { callback(new RelayError('KAM_RELAY_APK_SIZE')); return; }
      sha256.update(chunk); callback(null, chunk);
    }});
    const outputHandle = await fs.promises.open(partial, 'wx', 0o600);
    ownsPartial = true;
    const target = outputHandle.createWriteStream();
    try {
      await pipeline(handle.createReadStream({start: 0, end: expected.bytes - 1, autoClose: false}),
        decipher, counter, target);
    } catch { throw new RelayError('KAM_RELAY_DECRYPT_AUTH_OR_IO'); }
    need(bytes === expected.bytes && sha256.digest('hex') === expected.sha256, 'KAM_RELAY_APK_HASH');
    need(!fs.existsSync(output), 'KAM_RELAY_APK_OUTPUT_EXISTS');
    fs.renameSync(partial, output);
    ownsPartial = false;
  } finally {
    await handle.close();
    if (ownsPartial) fs.rmSync(partial, {force: true});
  }
}

async function decrypt(context, core) {
  const state = readState(context, 'FINALIZED');
  const input = process.env.KAM_ENCRYPTED_APK_PATH || '';
  const output = process.env.KAM_APK_PATH || '';
  const evidence = process.env.KAM_QA_OUTPUT || '';
  need(path.isAbsolute(input) && path.isAbsolute(output), 'KAM_RELAY_APK_PATHS');
  need(path.isAbsolute(evidence), 'KAM_RELAY_EVIDENCE_PATH');
  const key = decodeKey(state.payload_cipher?.key_b64, 32);
  const nonce = decodeKey(state.payload_cipher?.nonce_b64, 12);
  try { await decryptVerified(input, output, key, nonce, {bytes: APK_BYTES, sha256: APK_SHA256}); }
  finally { key.fill(0); nonce.fill(0); }
  fs.mkdirSync(evidence, {recursive: true});
  writePrivate(path.join(evidence, 'input-preparation.json'), {
    schema_version: 1, status: 'INPUT_APK_VERIFIED', route: 'encrypted Actions artifact',
    request_id: context.request_id, github_run_id: context.github_run_id,
    github_run_attempt: context.github_run_attempt, artifact_id: state.artifact_id,
    artifact_name: context.artifact_name, apk_bytes: APK_BYTES, apk_sha256: APK_SHA256,
    zip_bytes: state.receipt.zip_bytes, zip_sha256: state.receipt.zip_sha256,
    android_started: false, game_executed: false, finished_utc: new Date().toISOString()
  });
  fs.unlinkSync(context.state_path);
  core.setOutput('apk-path', output);
  core.info('Pinned APK authenticated and hash-verified; the relay key state was removed.');
}

async function main() {
  const core = await import('@actions/core');
  const context = runtimeContext(core.getInput('request-id', {required: true}));
  const mode = core.getInput('mode', {required: true});
  if (mode === 'prepare') await prepare(context, core);
  else if (mode === 'finalize') await finalize(context, core);
  else if (mode === 'decrypt') await decrypt(context, core);
  else throw new RelayError('KAM_RELAY_MODE');
}

if (require.main === module) {
  main().catch(error => {
    const code = error instanceof RelayError && SAFE_CODE.test(error.code) ? error.code : 'KAM_RELAY_INTERNAL';
    // Never print upstream messages/stacks: they may embed a SAS URL or a token.
    process.stderr.write(`::error::KaM encrypted input relay failed (${code}).\n`);
    process.exitCode = 1;
  });
}
module.exports = {encryptCapsule, validateReceipt, decryptVerified, TRANSPORT_AAD, APK_BYTES, APK_SHA256};

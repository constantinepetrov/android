'use strict';
// Offline protocol/authentication tests only. They never call Actions or ADB.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {encryptCapsule, validateReceipt, decryptVerified, TRANSPORT_AAD, APK_BYTES} = require('./main.cjs');

test('transport capsule authenticates and decrypts with the intended private key and AAD', () => {
  const {publicKey, privateKey} = crypto.generateKeyPairSync('rsa', {modulusLength: 2048});
  const capsule = {schema_version: 1, secret: 'local-only fixture', request_id: 'fixture'};
  const envelope = encryptCapsule(capsule, publicKey);
  assert.equal(envelope.key_fingerprint_sha256,
    crypto.createHash('sha256').update(publicKey.export({type: 'spki', format: 'der'})).digest('hex'));
  const key = crypto.privateDecrypt({key: privateKey, oaepHash: 'sha256',
    padding: crypto.constants.RSA_PKCS1_OAEP_PADDING}, Buffer.from(envelope.wrapped_key_b64, 'base64'));
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(envelope.iv_b64, 'base64'));
  decipher.setAAD(TRANSPORT_AAD);
  decipher.setAuthTag(Buffer.from(envelope.tag_b64, 'base64'));
  assert.deepEqual(JSON.parse(Buffer.concat([decipher.update(Buffer.from(envelope.ciphertext_b64, 'base64')),
    decipher.final()]).toString()), capsule);
  const wrongAad = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(envelope.iv_b64, 'base64'));
  wrongAad.setAAD(Buffer.from('wrong-context'));
  wrongAad.setAuthTag(Buffer.from(envelope.tag_b64, 'base64'));
  wrongAad.update(Buffer.from(envelope.ciphertext_b64, 'base64'));
  assert.throws(() => wrongAad.final());
  key.fill(0);
});

test('receipt rejects another run, wrong size/hash, numeric IDs and unexpected fields', () => {
  const context = {schema_version: 1, request_id: 'test-request', github_run_id: '123',
    github_run_attempt: '1', artifact_name: 'kam-encrypted-apk-123-1'};
  const receipt = {...context, zip_bytes: APK_BYTES + 160, zip_sha256: 'ab'.repeat(32)};
  assert.deepEqual(validateReceipt(receipt, context), receipt);
  for (const mutation of [{github_run_id: '999'}, {github_run_attempt: '2'}, {github_run_id: 123},
    {request_id: 'other'}, {artifact_name: 'other'}, {zip_bytes: APK_BYTES},
    {zip_bytes: APK_BYTES + 1024 * 1024 + 1}, {zip_bytes: 1.5}, {zip_sha256: 'bad'},
    {signed_upload_url: 'unexpected'}]) {
    assert.throws(() => validateReceipt({...receipt, ...mutation}, context));
  }
});

test('payload decrypt publishes only authenticated bytes with the exact expected hash', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'kam-relay-test-'));
  const input = path.join(directory, 'fixture.enc');
  const key = crypto.randomBytes(32);
  const nonce = crypto.randomBytes(12);
  const plain = crypto.randomBytes(1024 * 1024 + 17);
  const expected = {bytes: plain.length, sha256: crypto.createHash('sha256').update(plain).digest('hex')};
  const cipher = crypto.createCipheriv('aes-256-gcm', key, nonce);
  const encrypted = Buffer.concat([cipher.update(plain), cipher.final(), cipher.getAuthTag()]);
  fs.writeFileSync(input, encrypted);
  try {
    const validOutput = path.join(directory, 'verified.apk');
    await decryptVerified(input, validOutput, key, nonce, expected);
    assert.deepEqual(fs.readFileSync(validOutput), plain);
    await assert.rejects(decryptVerified(input, validOutput, key, nonce, expected), /OUTPUT_EXISTS/);
    const wrongHashOutput = path.join(directory, 'wrong-hash.apk');
    await assert.rejects(decryptVerified(input, wrongHashOutput, key, nonce,
      {...expected, sha256: '0'.repeat(64)}), /APK_HASH/);
    assert.equal(fs.existsSync(wrongHashOutput), false);
    assert.equal(fs.existsSync(wrongHashOutput + '.part'), false);
    encrypted[encrypted.length - 1] ^= 1;
    fs.writeFileSync(input, encrypted);
    const tamperedOutput = path.join(directory, 'tampered.apk');
    await assert.rejects(decryptVerified(input, tamperedOutput, key, nonce, expected), /DECRYPT_AUTH_OR_IO/);
    assert.equal(fs.existsSync(tamperedOutput), false);
    assert.equal(fs.existsSync(tamperedOutput + '.part'), false);
  } finally {
    key.fill(0);
    fs.rmSync(directory, {recursive: true, force: true});
  }
});

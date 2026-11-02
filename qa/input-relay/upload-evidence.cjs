'use strict';

// The SDK emits masking commands containing raw secrets to stdout. This helper
// runs as a captured child process, so suppress ALL SDK stdout/stderr rather than
// saving those control commands into a public evidence archive.
const safeOut = process.stdout.write.bind(process.stdout);
const safeErr = process.stderr.write.bind(process.stderr);
const discard = (chunk, encoding, callback) => {
  if (typeof encoding === 'function') encoding();
  if (typeof callback === 'function') callback();
  return true;
};
process.stdout.write = discard;
process.stderr.write = discard;
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const [directoryArg, sequenceArg] = process.argv.slice(2);
  const run = process.env.GITHUB_RUN_ID || '';
  const attempt = process.env.GITHUB_RUN_ATTEMPT || '';
  if (!/^[1-9][0-9]*$/.test(run) || !/^[1-9][0-9]*$/.test(attempt) ||
      !/^(0|[1-9][0-9]?)$/.test(sequenceArg || '') || Number(sequenceArg) > 30 ||
      process.env.GITHUB_REPOSITORY !== 'constantinepetrov/android') throw new Error('context');
  if (!path.isAbsolute(process.env.KAM_QA_OUTPUT || '')) throw new Error('evidence root');
  const root = fs.realpathSync(process.env.KAM_QA_OUTPUT);
  const directory = fs.realpathSync(directoryArg || '');
  if (!directory.startsWith(root + path.sep)) throw new Error('scope');
  const allowed = new Set(['.json', '.jsonl', '.log', '.txt', '.stdout', '.stderr', '.png', '.html']);
  const files = [];
  function visit(folder) {
    for (const name of fs.readdirSync(folder)) {
      if (name.startsWith('.')) throw new Error('hidden evidence');
      const file = path.join(folder, name);
      const stat = fs.lstatSync(file);
      if (stat.isSymbolicLink()) throw new Error('symlink');
      if (stat.isDirectory()) visit(file);
      else if (stat.isFile() && allowed.has(path.extname(name))) files.push(file);
      else throw new Error('not public evidence');
      if (files.length > 2000) throw new Error('evidence bounds');
    }
  }
  visit(directory);
  if (!files.length) throw new Error('empty evidence');
  const version = JSON.parse(fs.readFileSync(path.join(__dirname, 'node_modules/@actions/artifact/package.json'), 'utf8')).version;
  if (version !== '6.3.1') throw new Error('SDK version');
  const {DefaultArtifactClient} = await import('@actions/artifact');
  const name = `kam-ui-${run}-${attempt}-${sequenceArg}`;
  const result = await new DefaultArtifactClient().uploadArtifact(name, files, directory,
    {retentionDays: 7, compressionLevel: 6});
  if (!Number.isSafeInteger(result.id) || result.id <= 0) throw new Error('artifact id');
  safeOut(JSON.stringify({status: 'UI_EVIDENCE_UPLOADED', artifact_id: result.id,
    artifact_name: name, bytes: result.size, digest: result.digest}) + '\n');
}

main().catch(() => {
  safeErr('UI evidence upload failed; no credentials were included in diagnostics.\n');
  process.exitCode = 1;
});

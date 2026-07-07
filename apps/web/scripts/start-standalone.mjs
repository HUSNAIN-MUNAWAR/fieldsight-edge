import { cp, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const standaloneDir = path.join(appDir, '.next', 'standalone');
const staticSourceDir = path.join(appDir, '.next', 'static');
const staticTargetDir = path.join(standaloneDir, '.next', 'static');
const publicSourceDir = path.join(appDir, 'public');
const publicTargetDir = path.join(standaloneDir, 'public');

async function copyIfPresent(source, destination) {
  try {
    await access(source);
  } catch {
    return;
  }
  await cp(source, destination, { recursive: true, force: true });
}

await copyIfPresent(staticSourceDir, staticTargetDir);
await copyIfPresent(publicSourceDir, publicTargetDir);

const child = spawn(process.execPath, ['server.js'], {
  cwd: standaloneDir,
  stdio: 'inherit',
  env: process.env,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

const commands = [
  ['node_modules/typescript/bin/tsc', '-p', 'tsconfig.agent.json'],
  ['--experimental-strip-types', '--test', 'agent/tests/health.test.ts', 'agent/tests/service.test.ts', 'agent/tests/harness.test.ts'],
  ['node_modules/typescript/bin/tsc', '-p', 'showcase/tsconfig.json'],
  ['showcase/node_modules/vite/bin/vite.js', 'build', 'showcase'],
];
for (const args of commands) {
  const result = spawnSync(process.execPath, args, { stdio: 'inherit', env: { ...process.env, HEALTH_LLM_ENABLED: 'false' } });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
function scan(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) scan(path);
    else {
      if (/\.env|\.sqlite|\.pem$|\.key$|providers\.json|health-token/i.test(entry.name)) throw new Error(`Private file in public artifact: ${entry.name}`);
      if (/\.(js|json|html|css)$/.test(entry.name) && /sk-[a-zA-Z0-9_-]{16,}|Bearer [a-zA-Z0-9_.-]{24,}/.test(readFileSync(path, 'utf8'))) throw new Error(`Possible credential in public artifact: ${entry.name}`);
    }
  }
}
scan('showcase/dist');
console.log('Agent contracts, isolated harness, frontend and public credential boundary passed.');

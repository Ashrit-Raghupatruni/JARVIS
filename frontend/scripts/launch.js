/**
 * Launch script for electron-vite that clears ELECTRON_RUN_AS_NODE.
 *
 * VS Code (and other Electron-based IDEs) set ELECTRON_RUN_AS_NODE=1 in
 * their integrated terminals. This causes require('electron') to return
 * a file path instead of the Electron API module, crashing the app with:
 *   TypeError: Cannot read properties of undefined (reading 'requestSingleInstanceLock')
 *
 * This script clears that variable before spawning electron-vite,
 * working reliably across cmd.exe, PowerShell, and bash.
 */
const path = require('path');
const { spawn } = require('child_process');

// Clear the problematic variable
delete process.env.ELECTRON_RUN_AS_NODE;

// Forward all CLI args to electron-vite (e.g. "dev", "build", "preview")
const args = process.argv.slice(2);

// Programmatically resolve the electron-vite CLI binary path
let binPath;
try {
  const pkgPath = require.resolve('electron-vite/package.json');
  const pkgDir = path.dirname(pkgPath);
  const pkg = require(pkgPath);
  const binRelative = typeof pkg.bin === 'string' ? pkg.bin : pkg.bin['electron-vite'];
  binPath = path.resolve(pkgDir, binRelative);
} catch (e) {
  // Fallback to manual path resolution relative to this script
  binPath = path.resolve(__dirname, '../node_modules/electron-vite/bin/electron-vite.js');
}

const child = spawn(process.execPath, [binPath, ...args], {
  stdio: 'inherit',
  env: process.env
});

child.on('exit', (code) => process.exit(code ?? 0));

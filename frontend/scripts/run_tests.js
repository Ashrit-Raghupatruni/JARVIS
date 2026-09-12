const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Resolve path to the backend venv python executable
const rootDir = path.resolve(__dirname, '../..');
const backendDir = path.resolve(rootDir, 'backend');
let pythonPath = path.resolve(backendDir, 'venv', 'Scripts', 'python.exe');

// Fallback to standard python if venv executable is not found
if (!fs.existsSync(pythonPath)) {
  pythonPath = 'python';
}

const testScript = path.resolve(backendDir, 'tests', 'test_routes.py');

console.log(`Running route tests using python: ${pythonPath}`);
console.log(`Test script: ${testScript}`);

const child = spawn(pythonPath, ['-m', 'pytest', testScript], {
  stdio: 'inherit',
  cwd: rootDir,
  env: { ...process.env, PYTHONPATH: rootDir },
  shell: true
});

child.on('exit', (code) => {
  console.log(`Test process exited with code ${code}`);
  process.exit(code ?? 0);
});

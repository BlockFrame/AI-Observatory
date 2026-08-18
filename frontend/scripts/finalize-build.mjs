import fs from 'node:fs';
import path from 'node:path';

const frontendRoot = process.cwd();
const repositoryRoot = path.resolve(frontendRoot, '..');
const outputRoot = path.join(repositoryRoot, 'web');
const backupRoot = path.join(repositoryRoot, '.data-backup');

if (fs.existsSync(backupRoot)) {
	fs.cpSync(backupRoot, path.join(outputRoot, 'data'), { recursive: true });
	fs.rmSync(backupRoot, { recursive: true, force: true });
	console.log('Restored web/data');
}

for (const filename of ['llms.txt', 'ai-index.json']) {
	const source = path.join(repositoryRoot, filename);
	if (!fs.existsSync(source)) {
		throw new Error(`Required public metadata file is missing: ${filename}`);
	}
	fs.copyFileSync(source, path.join(outputRoot, filename));
	console.log(`Published ${filename}`);
}

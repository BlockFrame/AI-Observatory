import fs from 'fs';
import path from 'path';

export const prerender = true;

export function load() {
    const contentPath = path.resolve('../web/data/influencers.json');
    let htmlContent = null;

    if (fs.existsSync(contentPath)) {
        const data = JSON.parse(fs.readFileSync(contentPath, 'utf-8'));
        htmlContent = data.content || null;
    }

    return {
        htmlContent
    };
}

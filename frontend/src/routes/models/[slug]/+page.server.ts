import fs from 'fs';
import path from 'path';
import { slugify } from '$lib/utils/slugify';

export const prerender = true;

export function entries() {
    // SvelteKit runs this in the context of the `frontend` directory during `npm run build`
    const dataPath = path.resolve('../web/data/models.json');
    if (!fs.existsSync(dataPath)) {
        console.warn('models.json non trovato in', dataPath);
        return [];
    }
    const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    
    // We must ensure unique slugs so SvelteKit doesn't crash on duplicate entries
    const slugs = new Set(data.map((model: any) => slugify(model.name)));
    
    return Array.from(slugs).map(slug => ({
        slug
    }));
}

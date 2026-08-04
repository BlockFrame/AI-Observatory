import fs from 'fs';
import path from 'path';
import { slugify } from '$lib/utils/slugify';

export const prerender = true;

// Define entries for SSG
export function entries() {
    const dataPath = path.resolve('../web/data/models.json');
    if (!fs.existsSync(dataPath)) {
        return [];
    }
    const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    const slugs = new Set<string>(data.map((model: any) => slugify(model.name)));
    return Array.from(slugs).map(slug => ({ slug }));
}

// Load data at build time to pass directly to the page template
export function load({ params }) {
    const slug = params.slug;
    const modelsPath = path.resolve('../web/data/models.json');
    const contentPath = path.resolve('../web/data/models-content.json');

    let model = null;
    let htmlContent = null;

    if (fs.existsSync(modelsPath)) {
        const models = JSON.parse(fs.readFileSync(modelsPath, 'utf-8'));
        model = models.find((m: any) => slugify(m.name) === slug) || null;
    }

    if (model && fs.existsSync(contentPath)) {
        const contents = JSON.parse(fs.readFileSync(contentPath, 'utf-8'));
        htmlContent = contents[slug] || null;
    }

    return {
        model,
        htmlContent
    };
}

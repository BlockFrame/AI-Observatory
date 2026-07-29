import fs from 'fs';
import * as cheerio from 'cheerio';

function slugify(text) {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, '-')
        .replace(/[^\w\-]+/g, '')
        .replace(/\-\-+/g, '-')
        .replace(/^-+/, '')
        .replace(/-+$/, '');
}

async function run() {
    const dataPath = '../web/data/models.json';
    const outPath = '../web/data/models-content.json';
    
    const models = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    const contentMap = {};
    
    console.log(`Starting scraping for ${models.length} models...`);
    
    // We will process in batches of 10 to avoid too many concurrent connections
    const batchSize = 10;
    for (let i = 0; i < models.length; i += batchSize) {
        const batch = models.slice(i, i + batchSize);
        const promises = batch.map(async (model) => {
            try {
                const res = await fetch(model.url);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const html = await res.text();
                const $ = cheerio.load(html);
                
                // We extract the main content. ai-tldr.dev uses <article class="lrn-article">
                const content = $('.lrn-art-content').html();
                
                const slug = slugify(model.name);
                if (content) {
                    contentMap[slug] = content;
                    console.log(`[OK] ${model.name}`);
                } else {
                    console.log(`[NO CONTENT] ${model.name}`);
                }
            } catch (err) {
                console.error(`[ERROR] ${model.name}: ${err.message}`);
            }
        });
        
        await Promise.all(promises);
    }
    
    fs.writeFileSync(outPath, JSON.stringify(contentMap, null, 2));
    console.log(`Done! Saved to ${outPath}`);
}

run();

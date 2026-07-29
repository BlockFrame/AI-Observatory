import fs from 'fs';
import * as cheerio from 'cheerio';
import path from 'path';

async function run() {
    const outPath = path.resolve('../web/data/influencers.json');
    
    try {
        const res = await fetch("https://ai-tldr.dev/influencers/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const html = await res.text();
        const $ = cheerio.load(html);
        
        // Use the rls-article container to get the content
        const content = $('.rls-article').html();
        if (content) {
            fs.writeFileSync(outPath, JSON.stringify({ content }, null, 2));
            console.log(`[OK] Saved influencers to ${outPath}`);
        } else {
            console.log(`[NO CONTENT] Could not find influencer content.`);
        }
    } catch (err) {
        console.error(`[ERROR]: ${err.message}`);
    }
}

run();

import fs from 'fs';
import * as cheerio from 'cheerio';

async function run() {
    const dataPath = '../web/data/models.json';
    const models = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    
    // Test with the first 2 models
    for (const model of models.slice(0, 2)) {
        console.log(`Fetching ${model.url}...`);
        const res = await fetch(model.url);
        const html = await res.text();
        const $ = cheerio.load(html);
        
        const article = $('article.lrn-article').html();
        if (article) {
            console.log(`Found article for ${model.name}, length: ${article.length}`);
        } else {
            console.log(`NO article found for ${model.name}`);
        }
    }
}

run();

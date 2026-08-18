import { slugify } from '$lib/utils/slugify';
import models from '../../../static/data/models.json';
import tools from '../../../static/data/tools.json';
import { SITE } from '$lib/site';
import { categoryEntries, readDataIndex } from '$lib/server/briefingData';

export const prerender = true;

export async function GET() {
    const staticPages = [
        '',
        '/about',
        '/influencers',
        '/models',
        '/tools',
        '/archive'
    ];

    const modelPages = [...new Set(models.map((m: any) => `/models/${slugify(m.name)}`))];
    const index = readDataIndex();
    const briefingPages = [
        ...index.dates.map(({ date }) => `/briefings/${date}`),
        ...categoryEntries().map(({ date, category }) => `/briefings/${date}/${category}`)
    ];

    const allPages = [...staticPages, ...modelPages, ...briefingPages];
    const latestDate = index.latestDate ?? new Date().toISOString().slice(0, 10);

    const metadataFor = (page: string) => {
        const briefingMatch = page.match(/^\/briefings\/(\d{4}-\d{2}-\d{2})(?:\/[^/]+)?$/);
        if (briefingMatch) {
            const isLatest = briefingMatch[1] === index.latestDate;
            return {
                lastmod: briefingMatch[1],
                changefreq: isLatest ? 'daily' : 'monthly',
                priority: page.split('/').length === 3 ? '0.9' : '0.8'
            };
        }
        return {
            lastmod: latestDate,
            changefreq: page === '' ? 'daily' : 'weekly',
            priority: page === '' ? '1.0' : page.startsWith('/models/') ? '0.6' : '0.7'
        };
    };

    const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages.map(page => {
    const metadata = metadataFor(page);
    return `    <url>
        <loc>${SITE.url}${page}</loc>
        <lastmod>${metadata.lastmod}</lastmod>
        <changefreq>${metadata.changefreq}</changefreq>
        <priority>${metadata.priority}</priority>
    </url>`;
}).join('\n')}
</urlset>`;

    return new Response(sitemap, {
        headers: {
            'Content-Type': 'application/xml',
            'Cache-Control': 'max-age=0, s-maxage=3600'
        }
    });
}

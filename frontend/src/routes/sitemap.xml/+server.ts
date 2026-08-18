import { slugify } from '$lib/utils/slugify';
import models from '../../../static/data/models.json';
import tools from '../../../static/data/tools.json';
import { SITE } from '$lib/config/site';

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

    const allPages = [...staticPages, ...modelPages];

    const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages.map(page => `    <url>
        <loc>${SITE.url}${page}</loc>
        <changefreq>${page === '' ? 'daily' : 'weekly'}</changefreq>
        <priority>${page === '' ? '1.0' : (page.includes('/') ? '0.7' : '0.8')}</priority>
    </url>`).join('\n')}
</urlset>`;

    return new Response(sitemap, {
        headers: {
            'Content-Type': 'application/xml',
            'Cache-Control': 'max-age=0, s-maxage=3600'
        }
    });
}

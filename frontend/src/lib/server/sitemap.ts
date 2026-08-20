import { SITE } from '$lib/site';

export type SitemapUrl = {
	path: string;
	lastmod?: string;
};

export type SitemapDocument = {
	path: string;
	lastmod?: string;
};

function escapeXml(value: string): string {
	return value.replace(/[<>&'\"]/g, (character) => {
		const entities: Record<string, string> = {
			'<': '&lt;',
			'>': '&gt;',
			'&': '&amp;',
			"'": '&apos;',
			'"': '&quot;'
		};
		return entities[character];
	});
}

function absoluteUrl(path: string): string {
	return escapeXml(`${SITE.url}${path}`);
}

export function renderUrlSet(entries: SitemapUrl[]): string {
	const urls = entries
		.map(
			({ path, lastmod }) => `  <url>
    <loc>${absoluteUrl(path)}</loc>${lastmod ? `
    <lastmod>${escapeXml(lastmod)}</lastmod>` : ''}
  </url>`
		)
		.join('\n');

	return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>`;
}

export function renderSitemapIndex(entries: SitemapDocument[]): string {
	const sitemaps = entries
		.map(
			({ path, lastmod }) => `  <sitemap>
    <loc>${absoluteUrl(path)}</loc>${lastmod ? `
    <lastmod>${escapeXml(lastmod)}</lastmod>` : ''}
  </sitemap>`
		)
		.join('\n');

	return `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemaps}
</sitemapindex>`;
}

export function sitemapResponse(xml: string): Response {
	return new Response(xml, {
		headers: {
			'Content-Type': 'application/xml; charset=utf-8',
			'Cache-Control': 'max-age=0, s-maxage=3600'
		}
	});
}

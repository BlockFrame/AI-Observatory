import { readDataIndex } from '$lib/server/briefingData';
import { renderSitemapIndex, sitemapResponse } from '$lib/server/sitemap';

export const prerender = true;

export function GET() {
	const latestDate = readDataIndex().latestDate ?? undefined;
	return sitemapResponse(
		renderSitemapIndex([
			{ path: '/sitemaps/core.xml' },
			{ path: '/sitemaps/models.xml' },
			{ path: '/sitemaps/briefings.xml', lastmod: latestDate }
		])
	);
}

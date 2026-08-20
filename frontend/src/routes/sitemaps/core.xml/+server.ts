import { renderUrlSet, sitemapResponse } from '$lib/server/sitemap';

export const prerender = true;

export function GET() {
	return sitemapResponse(
		renderUrlSet(
			['', '/about', '/influencers', '/models', '/tools', '/archive'].map((path) => ({ path }))
		)
	);
}

import { slugify } from '$lib/utils/slugify';
import { renderUrlSet, sitemapResponse } from '$lib/server/sitemap';
import models from '../../../../static/data/models.json';

export const prerender = true;

export function GET() {
	const paths = [...new Set(models.map((model: { name: string }) => `/models/${slugify(model.name)}`))];
	return sitemapResponse(renderUrlSet(paths.map((path) => ({ path }))));
}

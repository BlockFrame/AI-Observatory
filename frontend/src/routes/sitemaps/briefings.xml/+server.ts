import {
	briefingEntries,
	categoryEntries
} from '$lib/server/briefingData';
import { renderUrlSet, sitemapResponse } from '$lib/server/sitemap';

export const prerender = true;

export function GET() {
	const briefingPages = briefingEntries().map(({ date }) => ({
		path: `/briefings/${date}`,
		lastmod: date
	}));
	const categoryPages = categoryEntries().map(({ date, category }) => ({
		path: `/briefings/${date}/${category}`,
		lastmod: date
	}));

	return sitemapResponse(renderUrlSet([...briefingPages, ...categoryPages]));
}

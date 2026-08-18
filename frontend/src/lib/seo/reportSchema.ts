import {
	CATEGORY_CONFIG,
	type Category,
	type CategoryData,
	type DaySummary
} from '$lib/types';
import { SITE, absoluteUrl } from '$lib/site';

export function reportStructuredData(summary: DaySummary, path: string) {
	const citations = Object.values(summary.categories ?? {})
		.flatMap((category) => category.top_items ?? [])
		.map((item) => item.url)
		.filter((url): url is string => /^https?:\/\//.test(url ?? ''))
		.filter((url, index, urls) => urls.indexOf(url) === index)
		.slice(0, 30);

	return {
		'@context': 'https://schema.org',
		'@type': 'Report',
		headline: `Daily AI Intelligence Briefing — ${summary.date}`,
		description: SITE.description,
		url: absoluteUrl(path),
		datePublished: summary.generated_at || summary.date,
		dateModified: summary.generated_at || summary.date,
		publisher: {
			'@type': 'Organization',
			name: SITE.parentName,
			url: SITE.parentUrl,
			logo: { '@type': 'ImageObject', url: absoluteUrl(SITE.imagePath) }
		},
		about: (summary.top_topics ?? []).map((topic) => ({
			'@type': 'Thing',
			name: topic.name
		})),
		citation: citations
	};
}

export function categoryStructuredData(
	summary: DaySummary,
	categoryData: CategoryData,
	category: Category,
	path: string
) {
	return {
		'@context': 'https://schema.org',
		'@type': 'CollectionPage',
		name: `${CATEGORY_CONFIG[category].title} Briefing — ${summary.date}`,
		description: categoryData.category_summary,
		url: absoluteUrl(path),
		datePublished: summary.generated_at || summary.date,
		isPartOf: { '@type': 'Report', url: absoluteUrl(`/briefings/${summary.date}`) },
		mainEntity: {
			'@type': 'ItemList',
			itemListElement: categoryData.items.map((item, index) => ({
				'@type': 'ListItem',
				position: index + 1,
				url: item.url,
				name: item.title
			}))
		}
	};
}

export function serializeStructuredData(value: unknown): string {
	return JSON.stringify(value).replace(/</g, '\\u003c');
}

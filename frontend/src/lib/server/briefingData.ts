import fs from 'node:fs';
import path from 'node:path';
import type {
	Category,
	CategoryData,
	CategorySummary,
	DataIndex,
	DateEntry,
	DaySummary,
	NewsItem
} from '$lib/types';

export const BRIEFING_CATEGORIES: Category[] = [
	'news',
	'research',
	'social',
	'github_trending'
];

function dataRoot(): string {
	const candidates = [
		path.resolve(process.cwd(), '../web/data'),
		path.resolve(process.cwd(), 'web/data')
	];
	const root = candidates.find((candidate) => fs.existsSync(candidate));
	if (!root) throw new Error('Could not locate web/data for briefing prerendering');
	return root;
}

function readJson<T>(filePath: string): T {
	return JSON.parse(fs.readFileSync(filePath, 'utf8')) as T;
}

export function readDataIndex(): DataIndex {
	const raw = readJson<Partial<DataIndex> & { dates?: DateEntry[] }>(
		path.join(dataRoot(), 'index.json')
	);
	const dates = raw.dates ?? [];
	return {
		schema_version: raw.schema_version,
		version: raw.version ?? '1.0',
		dates,
		latestDate: raw.latestDate ?? dates[0]?.date ?? null,
		generatedAt: raw.generatedAt ?? '',
		totalDates: raw.totalDates ?? dates.length
	};
}

export function briefingEntries(): Array<{ date: string }> {
	return readDataIndex().dates
		.filter(({ date }) => /^\d{4}-\d{2}-\d{2}$/.test(date))
		.filter(({ date }) => fs.existsSync(path.join(dataRoot(), date, 'summary.json')))
		.map(({ date }) => ({ date }));
}

export function categoryEntries(): Array<{ date: string; category: Category }> {
	return briefingEntries().flatMap(({ date }) =>
		BRIEFING_CATEGORIES.filter((category) =>
			fs.existsSync(path.join(dataRoot(), date, `${category}.json`))
		).map((category) => ({ date, category }))
	);
}

function compactItem(item: NewsItem): NewsItem {
	return {
		id: item.id,
		title: item.title,
		content: (item.content ?? '').slice(0, 500),
		url: item.url,
		author: item.author ?? '',
		published: item.published ?? '',
		source: item.source ?? '',
		source_type: item.source_type ?? '',
		summary: item.summary ?? '',
		summary_html: item.summary_html,
		importance_score: item.importance_score ?? 0,
		reasoning: '',
		tags: item.tags ?? [],
		themes: item.themes ?? [],
		freshness: item.freshness
	};
}

function compactCategorySummary(category?: CategorySummary): CategorySummary {
	if (!category) {
		return {
			count: 0,
			category_summary: '',
			themes: [],
			top_items: []
		};
	}
	return {
		count: category.count,
		current_item_ids: category.current_item_ids,
		analysis_quality: category.analysis_quality,
		category_summary: category.category_summary,
		category_summary_html: category.category_summary_html,
		category_summary_evidence: category.category_summary_evidence,
		themes: (category.themes ?? []).slice(0, 8),
		top_items: (category.top_items ?? []).slice(0, 5).map(compactItem)
	};
}

export function loadBriefing(date: string): DaySummary | null {
	const filePath = path.join(dataRoot(), date, 'summary.json');
	if (!fs.existsSync(filePath)) return null;
	const summary = readJson<DaySummary>(filePath);
	const categories = Object.fromEntries(
		BRIEFING_CATEGORIES.map((category) => [
			category,
			compactCategorySummary(summary.categories[category])
		])
	) as Record<Category, CategorySummary>;

	return {
		schema_version: summary.schema_version,
		date: summary.date,
		coverage_date: summary.coverage_date,
		coverage_start: summary.coverage_start,
		coverage_end: summary.coverage_end,
		executive_summary: summary.executive_summary,
		executive_summary_html: summary.executive_summary_html,
		top_topics: summary.top_topics ?? [],
		total_items_collected: summary.total_items_collected,
		total_items_analyzed: summary.total_items_analyzed,
		generated_at: summary.generated_at,
		categories,
		hero_image_url: summary.hero_image_url,
		collection_status: summary.collection_status,
		analysis_funnel: summary.analysis_funnel,
		executive_evidence_items: summary.executive_evidence_items,
		executive_summary_evidence: summary.executive_summary_evidence,
		quality_score: summary.quality_score
	};
}

export function loadBriefingCategory(date: string, category: Category): CategoryData | null {
	const filePath = path.join(dataRoot(), date, `${category}.json`);
	if (!fs.existsSync(filePath)) return null;
	const data = readJson<CategoryData>(filePath);
	return {
		...data,
		themes: (data.themes ?? []).slice(0, 12),
		// Keep prerendered HTML compact. BriefingCategory loads this same public
		// JSON file client-side and expands the list to every item.
		items: (data.items ?? []).slice(0, 12).map(compactItem)
	};
}

export function adjacentDates(date: string): { previousDate: string | null; nextDate: string | null } {
	const dates = readDataIndex().dates.map((entry) => entry.date);
	const index = dates.indexOf(date);
	return {
		previousDate: index >= 0 && index < dates.length - 1 ? dates[index + 1] : null,
		nextDate: index > 0 ? dates[index - 1] : null
	};
}

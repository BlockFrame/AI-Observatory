/**
 * Type definitions for the R[AI]DAR frontend
 */

export type Category = 'news' | 'research' | 'social' | 'github_trending';

export interface NewsItem {
	id: string;
	title: string;
	content: string;
	content_html?: string;
	url: string;
	author: string;
	published: string;
	source: string;
	source_type: string;
	tags: string[];
	summary: string;
	summary_html?: string;
	importance_score: number;
	reasoning: string;
	themes: string[];
	freshness?: {
		status: string;
		label: string;
		reason?: string;
		primary_url?: string;
		primary_published?: string;
		age_days?: number;
		exclude_from_top?: boolean;
	};
}

export interface CategoryTheme {
	name: string;
	description: string;
	item_count: number;
	example_items: string[];
	importance: number;
}

export interface TopTopic {
	name: string;
	description: string;
	description_html: string;
	business_implication?: string;
	business_implication_html?: string;
	trend_velocity?: string;
	category_breakdown: Record<Category, number>;
	representative_items: string[];
	importance: number;
}

export interface CategorySummary {
	count: number;
	current_item_ids?: string[];
	analysis_quality?: {
		source_items?: number;
		total_items: number;
		llm_analyzed_items: number;
		fallback_items: number;
		fallback_rate: number;
		skipped_by_budget?: number;
	};
	category_summary: string;
	category_summary_html?: string;
	category_summary_evidence?: string[][];
	themes: CategoryTheme[];
	top_items: NewsItem[];
}

export interface CollectionSource {
	name: string;
	display_name: string;
	status: 'success' | 'partial' | 'failed' | 'unknown';
	count: number;
	error: string | null;
	raw_count?: number;
	duration_ms?: number | null;
	duplicates_removed?: number;
	duplicate_rate?: number;
	fresh_items?: number | null;
	freshness_rate?: number | null;
	newest_item_at?: string | null;
	last_success_at?: string | null;
	last_nonempty_at?: string | null;
}

export interface CollectionStatus {
	overall: 'success' | 'partial' | 'failed' | 'unknown';
	sources: CollectionSource[];
}

export interface QualityScore {
	score: number;
	threshold: number;
	category_threshold: number;
	passed: boolean;
	components: Record<string, number>;
	failed_categories: string[];
	wiped_out_categories?: string[];
}

export interface AnalysisFunnelEntry {
	collected: number;
	analyzed: number;
	retention_rate: number | null;
	wipeout: boolean;
}

export interface DaySummary {
	schema_version?: string;
	date: string;
	coverage_date?: string;
	coverage_start?: string;
	coverage_end?: string;
	executive_summary: string;
	executive_summary_html?: string;
	top_topics: TopTopic[];
	total_items_collected: number;
	total_items_analyzed: number;
	generated_at: string;
	categories: Record<Category, CategorySummary>;
	hero_image_url?: string;
	collection_status?: CollectionStatus;
	analysis_funnel?: Record<Category, AnalysisFunnelEntry>;
	executive_evidence_items?: string[];
	executive_summary_evidence?: string[][];
	quality_score?: QualityScore;
}

export interface CategoryNotice {
	type: 'info' | 'warning';
	title: string;
	message: string;
}

export interface CategoryData {
	schema_version?: string;
	category: Category;
	date: string;
	category_summary: string;
	category_summary_html?: string;
	themes: CategoryTheme[];
	total_items: number;
	items: NewsItem[];
	notice?: CategoryNotice;
}

export interface DateEntry {
	date: string;
	total_items: number;
	categories: Record<Category, { count: number; file_size: number }>;
}

export interface DataIndex {
	schema_version?: string;
	version: string;
	dates: DateEntry[];
	latestDate: string | null;
	generatedAt: string;
	totalDates: number;
}

export interface SearchDocument {
	id: string;
	title: string;
	summary: string;
	url: string;
	date: string;
	category: Category;
	source: string;
	importance: number;
}

export interface SearchResult {
	ref: string;
	score: number;
	doc?: SearchDocument;
}

// Category display configuration
export const CATEGORY_CONFIG: Record<
	Category,
	{
		title: string;
		singularTitle: string;
		shortTitle: string;
		color: string;
		bgClass: string;
		textClass: string;
		badgeClass: string;
		accentClass: string;
	}
> = {
	news: {
		title: 'AI News',
		singularTitle: 'AI News',
		shortTitle: 'News',
		color: '#667eea',
		bgClass: 'bg-category-news',
		textClass: 'text-category-news',
		badgeClass: 'badge-news',
		accentClass: 'category-accent-news'
	},
	research: {
		title: 'Research',
		singularTitle: 'Research',
		shortTitle: 'Research',
		color: '#10b981',
		bgClass: 'bg-category-research',
		textClass: 'text-category-research',
		badgeClass: 'badge-research',
		accentClass: 'category-accent-research'
	},
	social: {
		title: 'Social Media',
		singularTitle: 'Social Media',
		shortTitle: 'Social',
		color: '#f59e0b',
		bgClass: 'bg-category-social',
		textClass: 'text-category-social',
		badgeClass: 'badge-social',
		accentClass: 'category-accent-social'
	},
	github_trending: {
		title: 'GitHub Trending Repos',
		singularTitle: 'GitHub Trending Repo',
		shortTitle: 'GitHub',
		color: '#8b5cf6',
		bgClass: 'bg-category-news',
		textClass: 'text-category-news',
		badgeClass: 'badge-news',
		accentClass: 'category-accent-news'
	}
};

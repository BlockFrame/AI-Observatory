<script lang="ts">
	import { page } from '$app/stores';
	import { goto, afterNavigate } from '$app/navigation';
	import { tick } from 'svelte';
	import { currentDate, isLoading as storeLoading, resolveLatestDate } from '$lib/stores/dateStore';
	import { loadDaySummary, loadCategoryData, preloadAdjacentDates } from '$lib/services/dataLoader';
	import { parseDate } from '$lib/services/dateUtils';
	import type { DaySummary, CategoryData, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import DateNavigator from '$lib/components/calendar/DateNavigator.svelte';
	import HeroSection from '$lib/components/layout/HeroSection.svelte';
	import ShaderBackground from '$lib/components/layout/ShaderBackground.svelte';
	import TopicCard from '$lib/components/news/TopicCard.svelte';
	import NewsList from '$lib/components/news/NewsList.svelte';
	import LoadingSpinner from '$lib/components/common/LoadingSpinner.svelte';
	import ErrorMessage from '$lib/components/common/ErrorMessage.svelte';
	import EmptyState from '$lib/components/common/EmptyState.svelte';
	import { safeHtml } from '$lib/services/safeHtml';

	// Data state
	let summary: DaySummary | null = null;
	let categoryData: CategoryData | null = null;
	let dataLoading = false;
	let error: string | null = null;
	let activeLoadId = 0;
	let lastHandledRouteKey = '';

	const validCategories: Category[] = ['news', 'research', 'social', 'reddit', 'github_trending'];

	// Read query params
	$: dateParam = $page.url.searchParams.get('date');
	$: rawCategoryParam = $page.url.searchParams.get('category');
	$: categoryParam =
		rawCategoryParam && validCategories.includes(rawCategoryParam as Category)
			? (rawCategoryParam as Category)
			: null;
	$: hasExplicitDate = dateParam !== null;
	$: routeKey = `${dateParam ?? 'latest'}|${rawCategoryParam ?? ''}`;

	// Validate params
	$: isValidDate = !hasExplicitDate || parseDate(dateParam ?? '') !== null;
	$: effectiveDate = hasExplicitDate ? (isValidDate ? dateParam : null) : ($currentDate || null);
	$: overviewHref = hasExplicitDate && effectiveDate ? `/?date=${effectiveDate}` : '/';
	$: categoryHref = (category: Category) =>
		hasExplicitDate && effectiveDate
			? `/?date=${effectiveDate}&category=${category}`
			: `/?category=${category}`;

	$: if (!$storeLoading && routeKey !== lastHandledRouteKey) {
		lastHandledRouteKey = routeKey;
		void handleRouteChange(dateParam, rawCategoryParam);
	}

	// Show loading when store is initializing OR when data is loading
	$: loading = $storeLoading || dataLoading;

	// Get category config for category view
	$: config = categoryParam ? CATEGORY_CONFIG[categoryParam] : null;

	// Scroll to hash anchor after navigation
	afterNavigate(async () => {
		if (typeof window === 'undefined') return;
		const hash = window.location.hash;
		if (!hash) return;

		await tick();
		setTimeout(() => {
			const element = document.getElementById(hash.slice(1));
			if (element) {
				element.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
		}, 150);
	});

	// Also handle scrolling after data loads
	$: if (!loading && (summary || categoryData) && typeof window !== 'undefined') {
		const hash = window.location.hash;
		if (hash) {
			setTimeout(() => {
				const element = document.getElementById(hash.slice(1));
				if (element) {
					element.scrollIntoView({ behavior: 'smooth', block: 'start' });
				}
			}, 150);
		}
	}

	async function handleRouteChange(rawDate: string | null, rawCategory: string | null) {
		if (rawCategory && !validCategories.includes(rawCategory as Category)) {
			const fallbackUrl = rawDate && parseDate(rawDate) ? `/?date=${rawDate}` : '/';
			goto(fallbackUrl, { replaceState: true });
			return;
		}

		if (rawDate && parseDate(rawDate) === null) {
			const fallbackUrl = rawCategory ? `/?category=${rawCategory}` : '/';
			goto(fallbackUrl, { replaceState: true });
			return;
		}

		const loadId = ++activeLoadId;
		error = null;

		const resolvedCategory = rawCategory as Category | null;
		const resolvedDate = rawDate ?? (await resolveLatestDate(true));
		if (loadId !== activeLoadId) {
			return;
		}

		if (!resolvedDate) {
			summary = null;
			categoryData = null;
			error = 'No reports available yet.';
			return;
		}

		currentDate.set(resolvedDate);
		await loadRouteData(resolvedDate, resolvedCategory, loadId);
	}

	async function loadRouteData(date: string, category: Category | null, loadId: number) {
		dataLoading = true;
		error = null;
		summary = null;
		categoryData = null;

		try {
			if (category) {
				const [summaryData, catData] = await Promise.all([
					loadDaySummary(date),
					loadCategoryData(date, category)
				]);

				if (loadId !== activeLoadId) {
					return;
				}

				summary = summaryData;
				categoryData = catData;
			} else {
				const summaryData = await loadDaySummary(date);
				if (loadId !== activeLoadId) {
					return;
				}

				summary = summaryData;
				preloadAdjacentDates(date);
			}
		} catch (e) {
			if (loadId !== activeLoadId) {
				return;
			}

			error = e instanceof Error ? e.message : 'Failed to load data';
			summary = null;
			categoryData = null;
		} finally {
			if (loadId === activeLoadId) {
				dataLoading = false;
			}
		}
	}

	function retry() {
		lastHandledRouteKey = '';
		void handleRouteChange(dateParam, rawCategoryParam);
	}

	// Format executive summary for display
	function formatExecutiveSummary(text: string, html?: string): string {
		if (html) {
			return html;
		}
		let formatted = text.replace(/^##\s*Executive Summary[^\n]*\n+/i, '');
		formatted = formatted.split(/\n\n+/).map(p => `<p class="mb-4 last:mb-0">${p.trim()}</p>`).join('');
		return formatted;
	}
</script>

<svelte:head>
	{#if categoryParam && config}
		<title>{config.title} - {effectiveDate || 'Latest'} | AI Observatory</title>
	{:else}
		<title>AI Observatory</title>
	{/if}
</svelte:head>

<div class="max-w-7xl mx-auto px-6 lg:px-10 py-8">
	{#if categoryParam && config}
		<!-- Category View Header -->
		<div
			class="card motion-card mb-8 border-l-[3px] p-7 text-white"
			style="border-left-color: {config.color}; background: linear-gradient(135deg, {config.color}18 0%, rgba(20, 27, 43, 0.72) 62%)"
		>
			<div class="flex items-center gap-3 mb-2">
				<a
					href={overviewHref}
					class="text-sm font-bold text-on-surface-variant transition-colors hover:text-white"
				>
					&larr; Back
				</a>
			</div>
			<p class="section-kicker">Category intelligence</p>
			<h1 class="text-3xl font-extrabold tracking-[-0.02em]">{config.title}</h1>
			{#if categoryData}
				<p class="mt-2 text-on-surface-variant">{categoryData.total_items} items for {effectiveDate}</p>
			{/if}
		</div>
	{/if}

	<!-- Date Navigator with coverage info -->
	<div class="mb-8">
		<DateNavigator coverageDate={summary?.coverage_date} />
	</div>

	{#if loading}
		<div class="py-20">
			<LoadingSpinner size="lg" />
		</div>
	{:else if error}
		<ErrorMessage title="Failed to load data" message={error} onRetry={retry} />
	{:else if categoryParam && categoryData}
		<!-- Category View -->
		<!-- Notice Banner (e.g., weekend arXiv notice) -->
		{#if categoryData.notice}
			<div
				class="mb-6 p-4 rounded-lg border-l-4 {categoryData.notice.type === 'info'
					? 'bg-blue-50 border-blue-400 text-blue-800 dark:bg-blue-900/30 dark:border-blue-500 dark:text-blue-200'
					: 'bg-amber-50 border-amber-400 text-amber-800 dark:bg-amber-900/30 dark:border-amber-500 dark:text-amber-200'}"
			>
				<div class="flex items-start gap-3">
					<svg
						class="w-5 h-5 flex-shrink-0 mt-0.5"
						fill="currentColor"
						viewBox="0 0 20 20"
					>
						<path
							fill-rule="evenodd"
							d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
							clip-rule="evenodd"
						/>
					</svg>
					<div>
						<p class="font-semibold">{categoryData.notice.title}</p>
						<p class="mt-1 text-sm opacity-90">{categoryData.notice.message}</p>
					</div>
				</div>
			</div>
		{/if}

		{#if categoryData.items.length === 0}
			<EmptyState
				title="No {config?.title.toLowerCase()} found"
				message="No items in this category for {effectiveDate}."
			/>
		{:else}
			<!-- Category Summary -->
			{#if categoryData.category_summary}
				<section class="mb-8">
					<div class="card motion-card border-l-[3px]" style="border-left-color: {config?.color}">
						<p class="section-kicker">{config?.shortTitle} intelligence</p>
						<h2 class="mb-5 text-2xl font-extrabold text-white">{config?.title} Summary</h2>
						<div class="prose-summary max-w-none">
							{@html safeHtml(categoryData.category_summary_html || categoryData.category_summary)}
						</div>
					</div>
				</section>
			{/if}

			<!-- Themes -->
			{#if categoryData.themes && categoryData.themes.length > 0}
				<section class="mb-8">
					<div class="section-heading">
						<div>
							<p class="section-kicker">Pattern detection</p>
							<h2 class="section-title">Key Themes</h2>
						</div>
					</div>
					<div class="flex flex-wrap gap-2">
						{#each categoryData.themes as theme}
							<span
								class="material-chip"
								style="border-color: {config?.color}40; color: {config?.color}"
							>
								{theme.name} ({theme.item_count})
							</span>
						{/each}
					</div>
				</section>
			{/if}

			<!-- All Items -->
			<section>
				<div class="section-heading">
					<div>
						<p class="section-kicker">Full coverage</p>
						<h2 class="section-title">All Items</h2>
					</div>
					<span class="material-chip">{categoryData.items.length} items</span>
				</div>
				<NewsList items={categoryData.items} category={categoryParam} date={effectiveDate || ''} />
			</section>
		{/if}
	{:else if summary}
		<!-- Overview View -->
		<!-- Custom Hero Section with Logo -->
		<section class="relative h-[500px] rounded-xl overflow-hidden mb-gutter group border border-white/10">
			<ShaderBackground className="opacity-40" />
			<div class="absolute inset-0 bg-gradient-to-br from-background/70 via-surface-container/60 to-background/90"></div>
			<div class="absolute inset-0 flex flex-col justify-end p-10">
				<!-- Live Indicator -->
				<div class="flex items-center gap-2 mb-4">
					<span class="flex h-3 w-3 rounded-full bg-secondary pulse-live"></span>
					<span class="font-label-caps text-label-caps text-secondary">LIVE INTELLIGENCE STREAM</span>
				</div>
				
				<!-- Title with Logo -->
				<div class="flex items-center gap-4 mb-4">
					<img src="/logo.png" alt="AI Observatory" class="w-12 h-12 rounded-lg" />
					<div>
						<h1 class="font-headline-xl text-headline-xl text-on-background leading-tight">AI Observatory</h1>
						<p class="font-body-sm text-body-sm text-on-surface-variant">Live Intelligence Feed</p>
					</div>
				</div>
				
				<!-- Description -->
				<p class="font-body-md text-body-md text-on-surface-variant max-w-2xl">
					Powered by Claude Opus 3.5. Real-time synthesized monitoring of {summary.total_items_analyzed} global neural developments, research breakthroughs, and social velocity metrics.
				</p>
			</div>
		</section>

		<!-- Original Hero Section (can be hidden/modified) -->
		<section class="mb-8 hidden">
			<HeroSection
				date={summary.date}
				coverageDate={summary.coverage_date}
				totalItems={summary.total_items_analyzed}
				heroImageUrl={summary.hero_image_url || null}
				collectionStatus={summary.collection_status?.overall || 'success'}
			/>
		</section>

		<!-- Executive Summary -->
		<section class="mb-12">
			<div class="section-heading">
				<div>
					<p class="section-kicker">Daily synthesis</p>
					<h2 class="section-title">Executive Summary</h2>
				</div>
				<span class="material-chip">
					<span class="h-2 w-2 rounded-full bg-tertiary shadow-[0_0_12px_rgba(78,222,163,0.65)]"></span>
					{summary.total_items_analyzed} items analyzed
				</span>
			</div>

			<div class="card motion-card overflow-visible border-l-[3px] border-l-primary p-7 sm:p-8">
				<div class="pointer-events-none absolute right-6 top-5 text-primary/10" aria-hidden="true">
					<svg class="h-20 w-20" fill="none" viewBox="0 0 96 96">
						<path d="M20 48h14l8-22 13 44 8-22h13" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
						<circle cx="48" cy="48" r="38" stroke="currentColor" stroke-width="2" />
					</svg>
				</div>
				<div class="executive-summary prose-summary relative max-w-none">
					{@html safeHtml(formatExecutiveSummary(summary.executive_summary, summary.executive_summary_html))}
				</div>
			</div>
		</section>

		<!-- Top Topics -->
		{#if summary.top_topics && summary.top_topics.length > 0}
			<section class="mb-12">
				<div class="section-heading">
					<div>
						<p class="section-kicker">Cross-category signals</p>
						<h2 class="section-title">Top Topics Today</h2>
					</div>
					<p class="section-copy">
						The strongest narratives detected across news, research, social media, and community discussion.
					</p>
				</div>
				<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
					{#each summary.top_topics as topic, index}
						<TopicCard {topic} animationIndex={index} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Category Sections -->
		{#each validCategories as category}
			{@const catSummary = summary.categories[category]}
			{#if catSummary && catSummary.top_items.length > 0}
				<section class="mb-12">
					<div class="section-heading">
						<div>
							<p class="section-kicker">Latest intelligence</p>
							<div class="flex items-center gap-3">
							<span
								class="w-3 h-3 rounded-full"
								style="background-color: {CATEGORY_CONFIG[category].color}"
							></span>
							<h2 class="section-title">
								{CATEGORY_CONFIG[category].title}
							</h2>
							<span class="material-chip">
								({catSummary.count} items)
							</span>
							</div>
						</div>
						<a
							href={categoryHref(category)}
							class="inline-flex items-center gap-2 text-sm font-bold text-primary transition-colors hover:text-white"
						>
							View All &rarr;
						</a>
					</div>

					<NewsList items={catSummary.top_items} {category} date={effectiveDate || ''} limit={5} totalCount={catSummary.count} />
				</section>
			{/if}
		{/each}
	{:else}
		<EmptyState
			title="No data available"
			message="Run the pipeline to generate news data."
		/>
	{/if}
</div>


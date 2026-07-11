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

	const validCategories: Category[] = ['news', 'research', 'social', 'reddit'];

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
			class="rounded-xl p-6 mb-8 text-white"
			style="background: linear-gradient(135deg, {config.color} 0%, {config.color}dd 100%)"
		>
			<div class="flex items-center gap-3 mb-2">
				<a
					href={overviewHref}
					class="text-white/80 hover:text-white transition-colors"
				>
					&larr; Back
				</a>
			</div>
			<h1 class="text-2xl font-bold">{config.title}</h1>
			{#if categoryData}
				<p class="text-white/80 mt-1">{categoryData.total_items} items for {effectiveDate}</p>
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
					<div class="card border-l-4" style="border-left-color: {config?.color}">
						<h2 class="font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-3">
							{config?.title} Summary
						</h2>
						<div class="prose-summary max-w-none">
							{@html safeHtml(categoryData.category_summary_html || categoryData.category_summary)}
						</div>
					</div>
				</section>
			{/if}

			<!-- Themes -->
			{#if categoryData.themes && categoryData.themes.length > 0}
				<section class="mb-8">
					<h2 class="font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-4">
						Key Themes
					</h2>
					<div class="flex flex-wrap gap-2">
						{#each categoryData.themes as theme}
							<span
								class="px-3 py-1.5 rounded-full text-sm font-medium"
								style="background-color: {config?.color}20; color: {config?.color}"
							>
								{theme.name} ({theme.item_count})
							</span>
						{/each}
					</div>
				</section>
			{/if}

			<!-- All Items -->
			<section>
				<h2 class="font-semibold text-trend-gray-800 dark:text-trend-gray-100 mb-6">
					All Items ({categoryData.items.length})
				</h2>
				<NewsList items={categoryData.items} category={categoryParam} date={effectiveDate || ''} />
			</section>
		{/if}
	{:else if summary}
		<!-- Overview View -->
		<!-- Custom Hero Section with Logo -->
		<section class="relative h-[500px] rounded-xl overflow-hidden mb-gutter group border border-white/10">
			<video
				autoplay
				muted
				loop
				playsinline
				class="absolute inset-0 h-full w-full object-cover opacity-25"
				src="https://ik.imagekit.io/lrigu76hy/tailark/dna-video.mp4?updatedAt=1745736251477"
			></video>
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
				<p class="font-body-md text-body-md text-on-surface-variant max-w-2xl mb-8">
					Powered by Claude Opus 3.5. Real-time synthesized monitoring of {summary.total_items_analyzed} global neural developments, research breakthroughs, and social velocity metrics.
				</p>
				
				<!-- Action Buttons -->
				<div class="flex gap-4 mb-6">
					<button class="bg-primary text-on-primary px-8 py-3 rounded-lg font-semibold shadow-xl shadow-primary/30 flex items-center gap-2 hover:brightness-110 transition-all">
						<span class="material-symbols-outlined">monitoring</span>
						View Live Matrix
					</button>
					<button class="glass-panel text-on-surface px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition-colors">
						Executive Summary
					</button>
				</div>

				<!-- Motion Brand Rail -->
				<div class="relative overflow-hidden rounded-md border border-white/10 bg-background/50 py-2">
					<div class="hero-brand-rail flex w-max items-center gap-8 px-4">
						<span class="hero-brand-pill">NVIDIA</span>
						<span class="hero-brand-pill">OPENAI</span>
						<span class="hero-brand-pill">GITHUB</span>
						<span class="hero-brand-pill">ANTHROPIC</span>
						<span class="hero-brand-pill">MICROSOFT</span>
						<span class="hero-brand-pill">META AI</span>
						<span class="hero-brand-pill">NVIDIA</span>
						<span class="hero-brand-pill">OPENAI</span>
						<span class="hero-brand-pill">GITHUB</span>
						<span class="hero-brand-pill">ANTHROPIC</span>
						<span class="hero-brand-pill">MICROSOFT</span>
						<span class="hero-brand-pill">META AI</span>
					</div>
				</div>
			</div>

			<!-- Ticker -->
			<div class="absolute bottom-0 w-full bg-surface-container-lowest/80 backdrop-blur-sm border-t border-white/5 py-2 overflow-hidden">
				<div class="ticker-scroll whitespace-nowrap flex items-center gap-10">
					<span class="font-data-mono text-data-mono text-tertiary">GPT-4.5 LAUNCH CONFIRMED +++ </span>
					<span class="font-data-mono text-data-mono text-electric-blue">CLAUDE OPUS LEADERS: 98.2% TASK SUCCESS +++ </span>
					<span class="font-data-mono text-data-mono text-secondary">OPEN SOURCE MOMENTUM: 2.7T PARAMETER MODELS +++ </span>
					<span class="font-data-mono text-data-mono text-tertiary">MULTIMODAL BREAKTHROUGHS: 92% ACCURACY +++ </span>
				</div>
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
			<div class="card border-l-4 border-trend-red dark:border-trend-red">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-xl font-bold text-trend-gray-800 dark:text-trend-gray-100">
						Executive Summary
					</h2>
					<span class="text-sm text-trend-gray-500 dark:text-trend-gray-400">
						{summary.total_items_analyzed} items analyzed
					</span>
				</div>
				<div class="prose-summary max-w-none">
					{@html safeHtml(formatExecutiveSummary(summary.executive_summary, summary.executive_summary_html))}
				</div>
			</div>
		</section>

		<!-- Top Topics -->
		{#if summary.top_topics && summary.top_topics.length > 0}
			<section class="mb-12">
				<h2 class="text-xl font-bold text-trend-gray-800 dark:text-trend-gray-100 mb-6">
					Top Topics Today
				</h2>
				<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
					{#each summary.top_topics as topic}
						<TopicCard {topic} />
					{/each}
				</div>
			</section>
		{/if}

		<!-- Category Sections -->
		{#each validCategories as category}
			{@const catSummary = summary.categories[category]}
			{#if catSummary && catSummary.top_items.length > 0}
				<section class="mb-12">
					<div class="flex items-center justify-between mb-6">
						<div class="flex items-center gap-3">
							<span
								class="w-3 h-3 rounded-full"
								style="background-color: {CATEGORY_CONFIG[category].color}"
							></span>
							<h2 class="text-xl font-bold text-trend-gray-800 dark:text-trend-gray-100">
								{CATEGORY_CONFIG[category].title}
							</h2>
							<span class="text-sm text-trend-gray-500">
								({catSummary.count} items)
							</span>
						</div>
						<a
							href={categoryHref(category)}
							class="text-sm font-medium text-trend-red hover:text-guardian-red transition-colors"
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

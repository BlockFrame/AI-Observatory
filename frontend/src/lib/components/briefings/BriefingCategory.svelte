<script lang="ts">
	import type { Category, CategoryData, DaySummary } from '$lib/types';
	import { browser } from '$app/environment';
	import { tick } from 'svelte';
	import { CATEGORY_CONFIG } from '$lib/types';
	import { formatDate } from '$lib/services/dateUtils';
	import { loadCategoryData } from '$lib/services/dataLoader';
	import { safeHtml } from '$lib/services/safeHtml';
	import { registerItems } from '$lib/services/itemIndex';
	import PageMeta from '$lib/components/seo/PageMeta.svelte';
	import NewsList from '$lib/components/news/NewsList.svelte';
	import LinkPreview from '$lib/components/news/LinkPreview.svelte';
	import { categoryStructuredData, serializeStructuredData } from '$lib/seo/reportSchema';

	export let summary: DaySummary;
	export let categoryData: CategoryData;
	export let category: Category;
	export let previousDate: string | null = null;
	export let nextDate: string | null = null;

	let displayItems = categoryData.items;
	let fullListLoading = false;
	let fullListError = '';
	let activeLoadKey = '';
	let visibleCount = 10;
	const PAGE_SIZE = 10;

	// SvelteKit reuses this component when navigating between category routes.
	// Keep all route-derived values reactive so headings and metadata cannot
	// remain bound to the category that was opened first.
	$: config = CATEGORY_CONFIG[category];
	$: path = `/briefings/${summary.date}/${category}`;
	$: title = `${config.title} Briefing`;
	$: reportDate = formatDate(summary.date, 'MMMM d, yyyy');
	$: pageTitle = `${title} — ${reportDate}`;
	$: description = `${config.title} intelligence for ${summary.date}, with ${categoryData.total_items} analyzed signals and direct source evidence.`;
	$: structuredData = serializeStructuredData(
		categoryStructuredData(summary, categoryData, category, path)
	);
	$: routeKey = `${summary.date}:${category}`;
	$: visibleItems = displayItems.slice(0, visibleCount);
	$: remainingItems = Math.max(0, displayItems.length - visibleCount);
	$: registerItems(summary.date, displayItems);
	$: if (browser && routeKey !== activeLoadKey) {
		activeLoadKey = routeKey;
		displayItems = categoryData.items;
		visibleCount = PAGE_SIZE;
		void loadAllItems(routeKey);
	}

	function revealHashTarget() {
		if (!browser || !window.location.hash.startsWith('#item-')) return;
		const targetId = window.location.hash.slice('#item-'.length);
		const targetIndex = displayItems.findIndex((item) => item.id === targetId);
		if (targetIndex >= 0) visibleCount = Math.max(visibleCount, targetIndex + 1);
	}

	function showMoreItems() {
		visibleCount = Math.min(displayItems.length, visibleCount + PAGE_SIZE);
	}

	async function loadAllItems(loadKey: string) {
		fullListLoading = categoryData.total_items > categoryData.items.length;
		fullListError = '';
		try {
			const completeCategory = await loadCategoryData(summary.date, category);
			if (loadKey !== activeLoadKey) return;
			displayItems = completeCategory.items ?? [];
			revealHashTarget();
			await tick();
			if (window.location.hash) {
				document
					.getElementById(window.location.hash.slice(1))
					?.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
		} catch {
			if (loadKey === activeLoadKey) {
				fullListError = 'The complete evidence list could not be loaded. Showing the top-ranked items.';
			}
		} finally {
			if (loadKey === activeLoadKey) fullListLoading = false;
		}
	}
</script>

<PageMeta title={pageTitle} {description} {path} type="article" />
<LinkPreview fallbackDate={summary.date} />

<svelte:head>
	{@html `<script type="application/ld+json">${structuredData}<\/script>`}
</svelte:head>

<div class="mx-auto max-w-7xl px-1 py-5 sm:px-6 sm:py-8 lg:px-10">
	<nav class="mb-6 flex flex-wrap items-center justify-between gap-4 text-sm" aria-label="Category briefing navigation">
		<a href="/briefings/{summary.date}" class="font-bold text-primary hover:text-white">&larr; Full briefing</a>
		<div class="flex items-center gap-3">
			{#if previousDate}<a href="/briefings/{previousDate}/{category}" class="material-chip">&larr; Previous</a>{/if}
			{#if nextDate}<a href="/briefings/{nextDate}/{category}" class="material-chip">Next &rarr;</a>{/if}
		</div>
	</nav>

	<header class="card mb-8 border-l-[3px] !p-5 sm:mb-10 sm:!p-9" style="border-left-color: {config.color}">
		<p class="section-kicker">Category intelligence</p>
		<h1 class="mt-2 text-3xl font-black tracking-[-0.035em] text-white sm:text-5xl">{title}</h1>
		<p class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-on-surface-variant">
			<span>All {categoryData.total_items} current items, analyzed and ranked.</span>
			<span class="hidden h-1 w-1 rounded-full bg-white/30 sm:inline-block" aria-hidden="true"></span>
			<time
				datetime={summary.date}
				class="text-xs font-bold uppercase tracking-[0.12em] text-on-surface-variant/80"
			>
				{reportDate}
			</time>
		</p>
	</header>

	{#if categoryData.category_summary_html || categoryData.category_summary}
		<section class="mb-10" aria-labelledby="category-summary">
			<div class="section-heading">
				<div>
					<p class="section-kicker">Executive synthesis</p>
					<h2 id="category-summary" class="section-title">{config.title} Summary</h2>
				</div>
			</div>
			<div class="card border-l-[3px] p-7" style="border-left-color: {config.color}">
				<div class="prose-summary max-w-none">
					{@html safeHtml(categoryData.category_summary_html || categoryData.category_summary)}
				</div>
			</div>
		</section>
	{/if}

	{#if categoryData.themes?.length}
		<section class="mb-10" aria-labelledby="key-themes">
			<h2 id="key-themes" class="section-title mb-4">Key Themes</h2>
			<div class="flex flex-wrap gap-2">
				{#each categoryData.themes as theme}
					<span class="material-chip">{theme.name} · {theme.item_count}</span>
				{/each}
			</div>
		</section>
	{/if}

	<section aria-labelledby="ranked-signals">
		<div class="section-heading">
			<div>
				<p class="section-kicker">Primary evidence</p>
				<h2 id="ranked-signals" class="section-title">All Ranked Signals</h2>
			</div>
		</div>
		{#if fullListLoading}
			<p class="mb-5 text-sm text-on-surface-variant" aria-live="polite">
				Loading all {categoryData.total_items} signals…
			</p>
		{:else if fullListError}
			<div class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-tertiary/30 bg-tertiary/10 px-4 py-3 text-sm text-on-surface-variant">
				<span>{fullListError}</span>
				<button class="font-bold text-primary hover:text-white" on:click={() => loadAllItems(routeKey)}>
					Retry
				</button>
			</div>
		{/if}
		<div class="mb-4 flex items-center justify-between gap-4 text-xs font-semibold text-on-surface-variant sm:text-sm">
			<span>Showing {Math.min(visibleCount, displayItems.length)} of {categoryData.total_items} signals</span>
			{#if !fullListLoading && remainingItems > 0}<span>{remainingItems} remaining</span>{/if}
		</div>
		<div
			class="mb-5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
			role="progressbar"
			aria-label="Ranked signals displayed"
			aria-valuemin="0"
			aria-valuemax={categoryData.total_items}
			aria-valuenow={Math.min(visibleCount, displayItems.length)}
		>
			<div
				class="h-full rounded-full bg-primary transition-[width] duration-300"
				style="width: {categoryData.total_items ? Math.min(100, (visibleCount / categoryData.total_items) * 100) : 0}%"
			></div>
		</div>
		<NewsList items={visibleItems} {category} date={summary.date} totalCount={categoryData.total_items} />
		{#if browser && !fullListLoading && remainingItems > 0}
			<div class="mt-6 flex justify-center">
				<button
					type="button"
					on:click={showMoreItems}
					class="min-h-[48px] w-full rounded-xl border border-primary/35 bg-primary/10 px-5 py-3 text-sm font-bold text-primary transition-colors hover:border-primary hover:bg-primary hover:text-on-primary sm:w-auto"
				>
					Load {Math.min(PAGE_SIZE, remainingItems)} more
				</button>
			</div>
		{/if}
	</section>
</div>

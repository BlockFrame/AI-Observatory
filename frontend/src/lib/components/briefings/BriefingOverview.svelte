<script lang="ts">
	import type { Category, DaySummary } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import { formatDate } from '$lib/services/dateUtils';
	import { safeHtml } from '$lib/services/safeHtml';
	import { registerItems } from '$lib/services/itemIndex';
	import PageMeta from '$lib/components/seo/PageMeta.svelte';
	import TopicCard from '$lib/components/news/TopicCard.svelte';
	import NewsList from '$lib/components/news/NewsList.svelte';
	import LinkPreview from '$lib/components/news/LinkPreview.svelte';
	import { reportStructuredData, serializeStructuredData } from '$lib/seo/reportSchema';

	export let summary: DaySummary;
	export let previousDate: string | null = null;
	export let nextDate: string | null = null;

	const categories: Category[] = ['news', 'research', 'social', 'github_trending'];
	const path = `/briefings/${summary.date}`;
	const title = `Daily AI Briefing — ${formatDate(summary.date, 'MMMM d, yyyy')}`;
	const description = `Executive AI intelligence briefing for ${summary.date}, synthesized from ${summary.total_items_analyzed} current news, research, social, and open-source signals.`;
	const structuredData = serializeStructuredData(reportStructuredData(summary, path));

	for (const category of categories) {
		registerItems(summary.date, summary.categories[category]?.top_items);
	}
</script>

<PageMeta {title} {description} {path} type="article" />
<LinkPreview fallbackDate={summary.date} />

<svelte:head>
	{@html `<script type="application/ld+json">${structuredData}<\/script>`}
</svelte:head>

<div class="mx-auto max-w-7xl px-6 py-8 lg:px-10">
	<nav class="mb-6 flex flex-wrap items-center justify-between gap-4 text-sm" aria-label="Briefing navigation">
		<a href="/archive" class="font-bold text-primary hover:text-white">&larr; Briefing archive</a>
		<div class="flex items-center gap-3">
			{#if previousDate}
				<a href="/briefings/{previousDate}" class="material-chip">&larr; Previous</a>
			{/if}
			{#if nextDate}
				<a href="/briefings/{nextDate}" class="material-chip">Next &rarr;</a>
			{:else}
				<a href="/" class="material-chip">Latest briefing</a>
			{/if}
		</div>
	</nav>

	<header class="card mb-10 border-l-[3px] border-l-primary p-7 sm:p-9">
		<p class="section-kicker">Daily AI intelligence</p>
		<h1 class="mt-2 text-4xl font-black tracking-[-0.035em] text-white sm:text-5xl">{title}</h1>
		<p class="mt-4 max-w-3xl text-base leading-relaxed text-on-surface-variant">
			{summary.total_items_analyzed} current signals analyzed across AI news, research, social media, and open-source projects.
		</p>
		<div class="mt-5 flex flex-wrap gap-2">
			{#each categories as category}
				<a href="/briefings/{summary.date}/{category}" class="material-chip">
					<span class="h-2 w-2 rounded-full" style="background-color: {CATEGORY_CONFIG[category].color}"></span>
					{CATEGORY_CONFIG[category].shortTitle} · {summary.categories[category]?.count ?? 0}
				</a>
			{/each}
		</div>
	</header>

	<section class="mb-12" aria-labelledby="executive-summary">
		<div class="section-heading">
			<div>
				<p class="section-kicker">Daily synthesis</p>
				<h2 id="executive-summary" class="section-title">Executive Summary</h2>
			</div>
		</div>
		<div class="card border-l-[3px] border-l-primary p-7 sm:p-8">
			<div class="executive-summary prose-summary max-w-none">
				{@html safeHtml(summary.executive_summary_html || summary.executive_summary)}
			</div>
		</div>
	</section>

	{#if summary.top_topics?.length}
		<section class="mb-12" aria-labelledby="top-topics">
			<div class="section-heading">
				<div>
					<p class="section-kicker">Cross-category signals</p>
					<h2 id="top-topics" class="section-title">Top Topics</h2>
				</div>
			</div>
			<div class="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
				{#each summary.top_topics as topic, index}
					<TopicCard {topic} animationIndex={index} />
				{/each}
			</div>
		</section>
	{/if}

	{#each categories as category}
		{@const categorySummary = summary.categories[category]}
		{#if categorySummary?.top_items?.length}
			<section class="mb-12" aria-labelledby="category-{category}">
				<div class="section-heading">
					<div>
						<p class="section-kicker">Current evidence</p>
						<h2 id="category-{category}" class="section-title">{CATEGORY_CONFIG[category].title}</h2>
					</div>
					<a href="/briefings/{summary.date}/{category}" class="font-bold text-primary hover:text-white">
						View category &rarr;
					</a>
				</div>
				{#if categorySummary.category_summary_html || categorySummary.category_summary}
					<div class="card mb-6 border-l-[3px] p-6" style="border-left-color: {CATEGORY_CONFIG[category].color}">
						<div class="prose-summary max-w-none">
							{@html safeHtml(categorySummary.category_summary_html || categorySummary.category_summary)}
						</div>
					</div>
				{/if}
				<NewsList items={categorySummary.top_items} {category} date={summary.date} limit={5} totalCount={categorySummary.count} />
			</section>
		{/if}
	{/each}
</div>

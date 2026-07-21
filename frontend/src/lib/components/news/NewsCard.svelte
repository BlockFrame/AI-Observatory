<script lang="ts">
	import type { NewsItem, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import { formatRelativeTime } from '$lib/services/dateUtils';
	import { markdownToHtml } from '$lib/services/markdown';
	import { safeHtml } from '$lib/services/safeHtml';
	import { isSafeUrl } from '$lib/services/sanitize';
	import CategoryBadge from './CategoryBadge.svelte';

	export let item: NewsItem;
	export let category: Category;
	export let date: string;
	export let showCategory: boolean = false;
	export let animationIndex: number = 0;

	let expanded = false;
	let copied = false;

	function copyShareLink() {
		const url = `${window.location.origin}/?date=${date}&category=${category}#item-${item.id}`;
		navigator.clipboard.writeText(url);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}

	$: config = CATEGORY_CONFIG[category];
	$: safeUrl = isSafeUrl(item.url) ? item.url : undefined;
	$: hasContent = item.content && item.content.length > 0;
	$: needsTruncation = item.content?.length > 300;
	$: freshness = item.freshness;

	// Use pre-rendered HTML if available, otherwise convert client-side
	$: summaryHtml = item.summary_html || markdownToHtml(item.summary || '');
	$: contentHtml = item.content_html || markdownToHtml(item.content || '');

	// Determine importance tier class
	$: importanceTierClass =
		item.importance_score >= 80
			? 'card-importance-high'
			: item.importance_score >= 60
				? 'card-importance-medium'
				: item.importance_score >= 40
					? 'card-importance-standard'
					: 'card-importance-low';
</script>

<article
	id="item-{item.id}"
	class="card motion-card group {importanceTierClass}"
	style="scroll-margin-top: 5rem; --motion-delay: {Math.min(animationIndex, 8) * 45}ms;"
>
	<div
		class="absolute inset-y-0 left-0 w-[3px] opacity-80 transition-opacity group-hover:opacity-100"
		style="background-color: {config.color}"
	></div>

	<header class="mb-5 flex items-start justify-between gap-5">
		<div class="min-w-0 flex-1">
			{#if showCategory}
				<CategoryBadge {category} class="mb-3" />
			{/if}

			<div class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-on-surface-variant">
				<span class="font-bold uppercase tracking-[0.14em]" style="color: {config.color}">
					{config.shortTitle}
				</span>
				<span class="h-1 w-1 rounded-full bg-white/25"></span>
				<span>{item.source}</span>
				{#if item.published}
					<span class="h-1 w-1 rounded-full bg-white/25"></span>
					<span>{formatRelativeTime(item.published)}</span>
				{/if}
				{#if freshness?.label}
					<span
						class="material-chip !px-2.5 !py-1 !text-[10px] !uppercase !tracking-[0.1em]"
						title={freshness.reason || freshness.label}
					>
						{freshness.label}
					</span>
				{/if}
			</div>

			<h3 class="text-xl font-extrabold leading-snug tracking-[-0.015em] text-white sm:text-2xl">
				<a
					href={safeUrl}
					target="_blank"
					rel="noopener noreferrer"
					class="transition-colors hover:text-primary"
				>
					{item.title}
				</a>
			</h3>

			{#if item.author}
				<p class="mt-2 text-xs text-on-surface-variant">By {item.author}</p>
			{/if}
		</div>

		<div
			class="flex h-12 w-12 flex-shrink-0 flex-col items-center justify-center rounded-2xl border border-white/10 text-sm font-extrabold shadow-inner
			       {item.importance_score >= 80
				? 'bg-secondary/10 text-secondary'
				: item.importance_score >= 60
					? 'bg-tertiary/10 text-tertiary'
					: 'bg-white/[0.04] text-on-surface-variant'}"
			title="Importance score: {item.importance_score}"
		>
			{Math.round(item.importance_score)}
			<span class="text-[8px] font-bold uppercase tracking-widest opacity-70">score</span>
		</div>
	</header>

	<!-- AI Analysis -->
	{#if item.summary}
		<div class="mb-5 rounded-2xl border border-white/5 bg-black/10 p-5">
			<div class="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-primary">
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 3v2m6.36.64-1.42 1.42M21 12h-2M5 12H3m4.05-4.95L5.64 5.64M9 18h6m-5 3h4m2.5-9a4.5 4.5 0 10-9 0c0 1.55.79 2.91 2 3.72V18h5v-2.28a4.48 4.48 0 002-3.72z" />
				</svg>
				<span>AI Analysis</span>
			</div>
			<div class="prose max-w-none text-[15px] leading-7">
				{@html safeHtml(summaryHtml)}
			</div>
		</div>
	{/if}

	<!-- Content (expandable) -->
	{#if hasContent}
		<div class="mb-5 text-sm text-on-surface-variant">
			<div
				class="prose max-w-none text-sm leading-6"
				class:line-clamp-3={!expanded && needsTruncation}
			>
				{@html safeHtml(contentHtml)}
			</div>

			{#if needsTruncation}
				<button
					on:click={() => (expanded = !expanded)}
					class="mt-3 rounded-full px-1 text-sm font-bold text-primary transition-colors hover:text-white"
				>
					{expanded ? 'Show less' : 'Read more'}
				</button>
			{/if}
		</div>
	{/if}

	<!-- Themes -->
	{#if item.themes && item.themes.length > 0}
		<div class="mb-5 flex flex-wrap gap-2">
			{#each item.themes as theme}
				<span class="material-chip">
					{theme}
				</span>
			{/each}
		</div>
	{/if}

	<!-- Actions -->
	<footer class="flex items-center justify-between gap-4 border-t border-white/5 pt-4">
		<a
			href={safeUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="inline-flex items-center gap-2 text-sm font-bold text-primary transition-colors hover:text-white"
		>
			{category === 'research' ? 'View Research' : category === 'reddit' ? 'View Discussion' : category === 'github_trending' ? 'View Repository' : 'Read More'}
			<span aria-hidden="true">&rarr;</span>
		</a>
		<button
			on:click={copyShareLink}
			class="material-chip transition-colors hover:border-primary/40 hover:text-white"
		>
			{copied ? 'Copied!' : 'Share'}
		</button>
	</footer>
</article>


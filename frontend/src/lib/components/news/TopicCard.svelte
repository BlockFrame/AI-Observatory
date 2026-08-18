<script lang="ts">
	import type { TopTopic, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import { safeHtml } from '$lib/services/safeHtml';

	export let topic: TopTopic;
	export let animationIndex: number = 0;

	$: categories = Object.entries(topic.category_breakdown || {})
		.filter(([_, count]) => count > 0)
		.map(([cat, count]) => [cat as Category, count] as [Category, number])
		.filter(([cat]) => CATEGORY_CONFIG[cat] !== undefined)
		.sort((a, b) => b[1] - a[1]);

	$: accentColor = categories.length > 0 ? CATEGORY_CONFIG[categories[0][0]].color : '#6366f1';
</script>

<article
	class="card motion-card relative flex h-full min-h-[360px] flex-col"
	style="border-left-color: {accentColor}; border-top-color: {accentColor}; border-left-width: 2px; --motion-delay: {Math.min(animationIndex, 8) * 65}ms;"
>
	<div class="pointer-events-none absolute right-4 top-3 opacity-[0.08]">
		<svg width="96" height="96" viewBox="0 0 96 96" fill="none" aria-hidden="true">
			<path
				d="M53 8L25 52H45L39 88L71 40H51L53 8Z"
				stroke={accentColor}
				stroke-width="4"
				stroke-linejoin="round"
			/>
		</svg>
	</div>

	<div class="mb-5 pr-12">
		<div class="flex items-center gap-2 mb-3">
			<p class="text-[11px] font-bold uppercase tracking-[0.2em] text-primary">
				Top Topic
			</p>
			{#if topic.trend_velocity}
				<span class="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
					{topic.trend_velocity}
				</span>
			{/if}
		</div>
		<h3 class="text-2xl font-extrabold leading-tight tracking-[-0.015em] text-white">
			{topic.name}
		</h3>
	</div>

	{#if topic.business_implication}
		<div class="mb-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
			<p class="mb-1 text-[11px] font-bold uppercase tracking-wider text-primary">Business Impact</p>
			<div class="prose-summary text-sm leading-relaxed text-white/90">
				{@html safeHtml(topic.business_implication_html || topic.business_implication)}
			</div>
		</div>
	{/if}

	<div class="flex-1 pr-2 prose-summary max-w-none text-sm leading-relaxed text-white/90">
		{@html safeHtml(topic.description_html || topic.description)}
	</div>

	<div class="mt-5 flex items-center justify-between gap-3 border-t border-white/5 pt-4">
		<div class="flex flex-wrap gap-2">
			{#each categories as [category, count]}
				{@const config = CATEGORY_CONFIG[category]}
				<span class="material-chip !px-2.5 !py-1 !text-[10px] !uppercase !tracking-[0.14em]">
					<span class="h-2 w-2 rounded-full" style="background-color: {config.color}"></span>
					{count} {config.shortTitle}
				</span>
			{/each}
		</div>

		<div
			class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-[rgba(99,102,241,0.18)] text-[#d9ddff] shadow-[0_10px_30px_rgba(99,102,241,0.18)]"
			aria-hidden="true"
		>
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
				<path
					d="M12 4C9.79 4 8 5.79 8 8C8 8.73 8.2 9.42 8.55 10.02C6.46 10.45 5 12.3 5 14.5C5 17.54 7.46 20 10.5 20C12.61 20 14.45 18.81 15.37 17.06C15.87 17.34 16.45 17.5 17.06 17.5C18.96 17.5 20.5 15.96 20.5 14.06C20.5 12.44 19.38 11.08 17.87 10.71C17.95 10.37 18 10.02 18 9.66C18 6.53 15.47 4 12.34 4H12Z"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
				<path
					d="M10.5 10.5L12.5 12.5M14.75 8.75L15.75 9.75M9 15.5L10.25 16.75"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
				/>
			</svg>
		</div>
	</div>
</article>

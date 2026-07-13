<script lang="ts">
	import type { TopTopic, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';

	export let topic: TopTopic;
	export let animationIndex: number = 0;

	type TopicBullet = {
		label: string;
		description: string;
		href?: string;
		color: string;
	};

	const BULLET_COLORS = ['#6366f1', '#4edea3', '#ffb3ad'];

	$: categories = Object.entries(topic.category_breakdown || {})
		.filter(([_, count]) => count > 0)
		.map(([cat, count]) => [cat as Category, count] as [Category, number])
		.filter(([cat]) => CATEGORY_CONFIG[cat] !== undefined)
		.sort((a, b) => b[1] - a[1]);

	$: accentColor = categories.length > 0 ? CATEGORY_CONFIG[categories[0][0]].color : '#6366f1';
	$: bullets = buildTopicBullets(topic);

	function buildTopicBullets(input: TopTopic): TopicBullet[] {
		const html = input.description_html || '';
		const text = normalizeWhitespace(stripHtml(html || input.description || ''));
		const sentences = splitSentences(text);
		const links = extractLinks(html);
		const results: TopicBullet[] = [];

		for (let i = 0; i < links.length && results.length < 3; i += 1) {
			const link = links[i];
			const sentence = sentences.find((entry) => entry.includes(link.text)) || link.text;
			const description = cleanupDescription(sentence.replace(link.text, ''));
			results.push({
				label: trimLabel(link.text),
				description: description || `Related development inside ${input.name.toLowerCase()}.`,
				href: link.href,
				color: BULLET_COLORS[i % BULLET_COLORS.length]
			});
		}

		for (let i = 0; i < sentences.length && results.length < 3; i += 1) {
			const sentence = sentences[i];
			if (!sentence || results.some((entry) => sentence.includes(entry.label))) {
				continue;
			}

			const label = extractLeadLabel(sentence, input.name);
			const description = cleanupDescription(sentence.replace(label, ''));
			results.push({
				label,
				description: description || sentence,
				color: BULLET_COLORS[results.length % BULLET_COLORS.length]
			});
		}

		return results.slice(0, 3);
	}

	function extractLinks(html: string): Array<{ href: string; text: string }> {
		const matches = [...html.matchAll(/<a[^>]*href="([^"]+)"[^>]*>(.*?)<\/a>/gi)];
		return matches.map((match) => ({
			href: decodeEntities(match[1]),
			text: normalizeWhitespace(stripHtml(match[2]))
		}));
	}

	function splitSentences(value: string): string[] {
		return value
			.split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
			.map((entry) => normalizeWhitespace(entry))
			.filter(Boolean);
	}

	function extractLeadLabel(sentence: string, fallback: string): string {
		const cleaned = cleanupDescription(sentence);
		const colonPrefix = cleaned.match(/^([^:]{3,40}):/);
		if (colonPrefix) {
			return trimLabel(colonPrefix[1]);
		}

		const entityMatch = cleaned.match(
			/\b([A-Z][A-Za-z0-9.+-]*(?:\s+[A-Z0-9][A-Za-z0-9.+-]*){0,2})\b/
		);
		if (entityMatch) {
			return trimLabel(entityMatch[1]);
		}

		return trimLabel(fallback);
	}

	function cleanupDescription(value: string): string {
		return normalizeWhitespace(
			value
				.replace(/^[\s:;,\-–—]+/, '')
				.replace(/[\s:;,\-–—]+$/, '')
		);
	}

	function trimLabel(value: string): string {
		return normalizeWhitespace(value).replace(/[.,;:!?]+$/, '');
	}

	function stripHtml(value: string): string {
		return decodeEntities(value.replace(/<[^>]+>/g, ' '));
	}

	function normalizeWhitespace(value: string): string {
		return value.replace(/\s+/g, ' ').trim();
	}

	function decodeEntities(value: string): string {
		return value
			.replace(/&amp;/g, '&')
			.replace(/&quot;/g, '"')
			.replace(/&#39;/g, "'")
			.replace(/&lt;/g, '<')
			.replace(/&gt;/g, '>');
	}
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
		<p class="mb-3 text-[11px] font-bold uppercase tracking-[0.2em] text-primary">
			Top Topic
		</p>
		<h3 class="text-2xl font-extrabold leading-tight tracking-[-0.015em] text-white">
			{topic.name}
		</h3>
	</div>

	<ul class="flex flex-1 flex-col gap-5 pr-2">
		{#each bullets as bullet}
			<li class="flex items-start gap-3">
				<span
					class="mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full"
					style="background-color: {bullet.color}"
				></span>
				<div class="min-w-0 space-y-1">
					{#if bullet.href}
						<a
							href={bullet.href}
							class="text-sm font-extrabold text-white underline decoration-transparent underline-offset-4 transition-colors hover:text-primary hover:decoration-primary"
						>
							{bullet.label}
						</a>
					{:else}
						<p class="text-sm font-extrabold text-white">
							{bullet.label}
						</p>
					{/if}
					<p class="text-sm leading-6 text-on-surface-variant/90">
						{bullet.description}
					</p>
				</div>
			</li>
		{/each}
	</ul>

	<div class="mt-5 flex items-center justify-between gap-3 border-t border-white/5 pt-4">
		<div class="flex flex-wrap gap-2">
			{#each categories.slice(0, 2) as [category, count]}
				{@const config = CATEGORY_CONFIG[category]}
				<span class="material-chip !px-2.5 !py-1 !text-[10px] !uppercase !tracking-[0.14em]">
					<span class="h-2 w-2 rounded-full" style="background-color: {config.color}"></span>
					{count} {config.shortTitle}
				</span>
			{/each}
		</div>

		<div
			class="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-[rgba(99,102,241,0.18)] text-[#d9ddff] shadow-[0_10px_30px_rgba(99,102,241,0.18)]"
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

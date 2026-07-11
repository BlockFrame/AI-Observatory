<script lang="ts">
	import { onMount } from 'svelte';

	let data: any = { news: [], research: [], social: [], reddit: [] };
	let activeTab = 'all';
	let searchQuery = '';

	onMount(async () => {
		try {
			const response = await fetch('/data/news_data.json');
			if (response.ok) {
				const rawData = await response.json();
				
				// Mappi categories per tab
				data.news = rawData.filter((item: any) => item.category === 'news').slice(0, 20);
				data.research = rawData.filter((item: any) => item.category === 'research').slice(0, 20);
				data.social = rawData.filter((item: any) => item.category === 'social').slice(0, 20);
				data.reddit = rawData.filter((item: any) => item.category === 'reddit').slice(0, 20);
			}
		} catch (error) {
			console.error('Error loading data:', error);
		}
	});

	function getFilteredItems() {
		switch (activeTab) {
			case 'research':
				return data.research.filter((item: any) => searchQuery === '' || item.title.toLowerCase().includes(searchQuery.toLowerCase()));
			case 'social':
				return data.social.filter((item: any) => searchQuery === '' || item.title.toLowerCase().includes(searchQuery.toLowerCase()));
			case 'reddit':
				return data.reddit.filter((item: any) => searchQuery === '' || item.title.toLowerCase().includes(searchQuery.toLowerCase()));
			default:
				return data.news.filter((item: any) => searchQuery === '' || item.title.toLowerCase().includes(searchQuery.toLowerCase()));
		}
	}

	function getTopStory() {
		return data.news && data.news.length > 0 ? data.news[0] : null;
	}

	function getKeyDevelopments() {
		return data.news.slice(1, 4);
	}

	$: filteredItems = getFilteredItems();
</script>

<!-- Hero Section -->
<section class="relative h-[500px] rounded-xl overflow-hidden mb-gutter group">
	<div class="absolute inset-0 bg-gradient-to-br from-primary/10 via-surface-container to-background"></div>
	<div class="absolute inset-0 flex flex-col justify-end p-10">
		<div class="flex items-center gap-2 mb-4">
			<span class="flex h-3 w-3 rounded-full bg-secondary pulse-live"></span>
			<span class="font-label-caps text-label-caps text-secondary">LIVE INTELLIGENCE STREAM</span>
		</div>
		<h2 class="font-headline-xl text-headline-xl text-on-background mb-2">AI Observatory</h2>
		<p class="font-body-md text-body-md text-on-surface-variant max-w-2xl mb-8">
			Real-time synthesized monitoring of global AI developments, research breakthroughs, and social velocity metrics.
		</p>
		<div class="flex gap-4">
			<button class="bg-primary text-on-primary px-8 py-3 rounded-lg font-semibold shadow-xl shadow-primary/30 flex items-center gap-2 hover:brightness-110 transition-all">
				<span class="material-symbols-outlined">monitoring</span>
				View Live Matrix
			</button>
			<button class="glass-panel text-on-surface px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition-colors">
				Executive Summary
			</button>
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

<!-- Executive Summary Grid -->
<section class="mb-gutter">
	<div class="flex items-center justify-between mb-6">
		<h3 class="font-label-caps text-label-caps text-outline uppercase">Executive Summary</h3>
		<span class="font-data-mono text-xs text-primary-fixed-dim">{data.news.length} items analyzed</span>
	</div>
	<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
		<!-- Top Story -->
		{#if getTopStory()}
			<div class="md:col-span-2 glass-panel p-8 rounded-xl neon-border-primary transition-all group">
				<div class="flex items-center justify-between mb-6">
					<h4 class="font-headline-lg text-headline-lg text-primary">Top Story</h4>
					<span class="bg-primary/20 text-primary px-3 py-1 rounded-full text-xs font-bold">URGENT</span>
				</div>
				<p class="font-body-md text-lg leading-relaxed text-on-surface mb-6">
					{getTopStory().title}
				</p>
				<div class="grid grid-cols-2 gap-4">
					<div class="bg-surface-container/50 p-4 rounded-lg border border-white/5">
						<span class="block font-label-caps text-[10px] text-outline mb-1">CATEGORY</span>
						<span class="font-data-mono text-xl text-tertiary capitalize">{getTopStory().category}</span>
					</div>
					<div class="bg-surface-container/50 p-4 rounded-lg border border-white/5">
						<span class="block font-label-caps text-[10px] text-outline mb-1">SOURCE</span>
						<span class="font-data-mono text-xl text-electric-blue">{getTopStory().source || 'AI News'}</span>
					</div>
				</div>
			</div>
		{/if}

		<!-- Key Developments -->
		<div class="glass-panel p-6 rounded-xl border-l-2 border-secondary overflow-hidden relative">
			<div class="absolute -right-4 -top-4 opacity-10">
				<span class="material-symbols-outlined text-8xl" style="font-variation-settings: 'FILL' 1;">bolt</span>
			</div>
			<h4 class="font-label-caps text-label-caps text-secondary mb-4">KEY DEVELOPMENTS</h4>
			<ul class="space-y-4">
				{#each getKeyDevelopments() as item}
					<li class="flex gap-3">
						<span class="text-secondary mt-1 text-xs">●</span>
						<p class="text-sm text-on-surface-variant">
							<strong class="text-on-surface">{item.title.substring(0, 50)}...</strong>
						</p>
					</li>
				{/each}
			</ul>
		</div>
	</div>
</section>

<!-- Main Feed Tabs -->
<div class="flex gap-8 border-b border-outline-variant/20 mb-8 overflow-x-auto">
	<button
		on:click={() => activeTab = 'all'}
		class="pb-4 px-2 border-b-2 {activeTab === 'all' ? 'border-primary text-primary font-bold' : 'border-transparent text-on-surface-variant hover:text-on-surface'} flex items-center gap-2 transition-colors"
	>
		<span class="material-symbols-outlined">newspaper</span> All News
	</button>
	<button
		on:click={() => activeTab = 'research'}
		class="pb-4 px-2 border-b-2 {activeTab === 'research' ? 'border-primary text-primary font-bold' : 'border-transparent text-on-surface-variant hover:text-on-surface'} flex items-center gap-2 transition-colors"
	>
		<span class="material-symbols-outlined">science</span> Research
	</button>
	<button
		on:click={() => activeTab = 'social'}
		class="pb-4 px-2 border-b-2 {activeTab === 'social' ? 'border-primary text-primary font-bold' : 'border-transparent text-on-surface-variant hover:text-on-surface'} flex items-center gap-2 transition-colors"
	>
		<span class="material-symbols-outlined">forum</span> Social Media
	</button>
	<button
		on:click={() => activeTab = 'reddit'}
		class="pb-4 px-2 border-b-2 {activeTab === 'reddit' ? 'border-primary text-primary font-bold' : 'border-transparent text-on-surface-variant hover:text-on-surface'} flex items-center gap-2 transition-colors"
	>
		<span class="material-symbols-outlined">edit</span> Discussions
	</button>
</div>

<!-- Vertically Stacked Feed -->
<div class="space-y-6 pb-20">
	{#each filteredItems as item (item.title)}
		<article class="glass-panel p-6 rounded-xl hover:bg-surface-container-high transition-colors group">
			<div class="flex flex-col md:flex-row gap-6">
				<div class="md:w-1/4 h-32 rounded-lg bg-surface-container overflow-hidden flex-shrink-0">
					<div class="w-full h-full bg-gradient-to-br from-primary/20 to-tertiary/20 flex items-center justify-center">
						<span class="material-symbols-outlined text-4xl text-primary/40">image</span>
					</div>
				</div>
				<div class="flex-1">
					<div class="flex items-center gap-3 mb-2">
						<span class="bg-surface-container-highest text-on-surface-variant px-2 py-0.5 rounded text-[10px] font-label-caps uppercase">{item.category}</span>
						<span class="text-outline text-xs">{item.source || 'AI News'}</span>
					</div>
					<h4 class="font-headline-lg-mobile text-headline-lg-mobile text-on-surface mb-2 group-hover:text-primary transition-colors">
						{item.title}
					</h4>
					<p class="text-sm text-on-surface-variant line-clamp-2 mb-4">
						{item.description || item.summary || 'No description available'}
					</p>
					<div class="flex items-center justify-between">
						<div class="flex gap-2 flex-wrap">
							{#if item.tags}
								{#each item.tags.slice(0, 3) as tag}
									<span class="bg-surface-variant/40 px-2 py-1 rounded text-[10px] border border-outline-variant/30">
										{tag}
									</span>
								{/each}
							{/if}
						</div>
						<button class="text-primary hover:underline text-sm font-semibold flex items-center gap-1">
							Read More
							<span class="material-symbols-outlined text-sm">arrow_forward</span>
						</button>
					</div>
				</div>
			</div>
		</article>
	{/each}

	{#if filteredItems.length === 0}
		<div class="glass-panel p-12 rounded-xl text-center">
			<span class="material-symbols-outlined text-6xl text-surface-variant/50 flex justify-center mb-4">search_off</span>
			<p class="text-on-surface-variant">No items found for your search</p>
		</div>
	{/if}
</div>

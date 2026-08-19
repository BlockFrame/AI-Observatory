<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { SearchResult, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import { formatDate } from '$lib/services/dateUtils';

	export let results: SearchResult[];
	export let selectedIndex: number = -1;

	const dispatch = createEventDispatcher();

	// Map old category names for backwards compatibility
	const categoryMapping: Record<string, Category> = {
		papers: 'research'
	};

	function getMappedCategory(cat: string): Category {
		return (categoryMapping[cat] || cat) as Category;
	}

	function handleClick(result: SearchResult) {
		dispatch('select', result);
	}
</script>

<div
	class="absolute z-[60] mt-2 max-h-[32rem] w-full overflow-y-auto rounded-xl border border-[#2b3655] bg-[#111d33] shadow-2xl"
>
	<ul class="py-2">
		{#each results as result, i (result.ref)}
			{@const doc = result.doc}
			{#if doc}
				{@const mappedCategory = getMappedCategory(doc.category)}
				{@const config = CATEGORY_CONFIG[mappedCategory]}
				<li>
					<button
						on:click={() => handleClick(result)}
						class="w-full px-4 py-3 text-left transition-colors hover:bg-[#1b2437]
						       {i === selectedIndex ? 'bg-[#1b2437]' : ''}"
					>
						<div class="flex items-start gap-3">
							<!-- Category indicator -->
							<span
								class="mt-1 w-2 h-2 rounded-full flex-shrink-0"
								style="background-color: {config.color}"
							></span>

							<div class="flex-1 min-w-0">
								<!-- Title -->
								<p class="line-clamp-1 font-medium text-white">
									{doc.title}
								</p>

								<!-- Summary preview -->
								{#if doc.summary}
									<p class="mt-1 line-clamp-2 text-sm text-[#b2b8cf]">
										{doc.summary}
									</p>
								{/if}

								<!-- Metadata -->
								<div class="mt-2 flex items-center gap-2 text-xs text-[#8e94ae]">
									<span class="badge {config.badgeClass}">
										{config.title}
									</span>
									<span>{doc.source}</span>
									<span>&middot;</span>
									<span>{formatDate(doc.date, 'MMM d')}</span>
								</div>
							</div>

							<!-- Score indicator -->
							<span
								class="rounded bg-white/[0.06] px-1.5 py-0.5 text-xs text-[#b2b8cf]"
								title="Relevance score"
							>
								{Math.round(doc.importance)}
							</span>
						</div>
					</button>
				</li>
			{/if}
		{/each}
	</ul>

	{#if results.length > 0}
		<div class="border-t border-white/10 px-4 py-2">
			<p class="text-center text-xs text-[#8e94ae]">
				{results.length} result{results.length === 1 ? '' : 's'} found
			</p>
		</div>
	{/if}
</div>

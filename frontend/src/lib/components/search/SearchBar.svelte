<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { goto } from '$app/navigation';
	import { search, initializeSearch, isSearchInitialized } from '$lib/services/searchIndex';
	import type { SearchResult, Category } from '$lib/types';
	import { CATEGORY_CONFIG } from '$lib/types';
	import SearchResults from './SearchResults.svelte';

	const dispatch = createEventDispatcher();

	export let placeholder = 'Search articles, research, discussions...';
	export let autofocus = false;
	export let showCategoryFilter = false;

	let query = '';
	let category: Category | '' = '';
	let results: SearchResult[] = [];
	let isOpen = false;
	let isLoading = false;
	let isReady = false;
	let initializationFailed = false;
	let selectedIndex = -1;
	let inputElement: HTMLInputElement;

	const categories: (Category | '')[] = ['', 'news', 'research', 'social', 'github_trending'];

	// Initialize search on mount
	onMount(async () => {
		isLoading = true;
		isReady = await initializeSearch();
		initializationFailed = !isReady;
		isLoading = false;
		// A user may type while the 30-day corpus is still loading. Re-run the
		// pending query once initialization completes instead of silently showing
		// an empty result set forever.
		if (isReady && query.length >= 2) await performSearch();
		if (autofocus && inputElement) {
			inputElement.focus();
		}
	});

	// Debounced search
	let searchTimeout: ReturnType<typeof setTimeout>;
	$: {
		clearTimeout(searchTimeout);
		if (query.length >= 2) {
			searchTimeout = setTimeout(() => {
				performSearch();
			}, 150);
		} else {
			results = [];
			isLoading = false;
		}
	}

	async function performSearch() {
		const currentQuery = query;
		isLoading = true;
		const ready = isSearchInitialized() || (await initializeSearch());
		isReady = ready;
		initializationFailed = !ready;
		if (!ready) {
			results = [];
			isLoading = false;
			return;
		}
		const found = await search(query, category || undefined);
		// Ignore stale responses if the query changed while awaiting.
		if (currentQuery !== query) {
			isLoading = false;
			return;
		}
		results = found;
		selectedIndex = -1;
		isLoading = false;
	}

	function handleFocus() {
		isOpen = true;
	}

	function handleBlur(event: FocusEvent) {
		// Delay closing to allow click on results
		setTimeout(() => {
			const target = event.relatedTarget as HTMLElement;
			if (!target?.closest('.search-container')) {
				isOpen = false;
			}
		}, 200);
	}

	function handleKeydown(event: KeyboardEvent) {
		switch (event.key) {
			case 'ArrowDown':
				event.preventDefault();
				selectedIndex = Math.min(selectedIndex + 1, results.length - 1);
				break;
			case 'ArrowUp':
				event.preventDefault();
				selectedIndex = Math.max(selectedIndex - 1, -1);
				break;
			case 'Enter':
				event.preventDefault();
				if (selectedIndex >= 0 && results[selectedIndex]) {
					selectResult(results[selectedIndex]);
				}
				break;
			case 'Escape':
				isOpen = false;
				inputElement?.blur();
				break;
		}
	}

	function selectResult(result: SearchResult) {
		if (result.doc) {
			goto(`/briefings/${result.doc.date}/${result.doc.category}#item-${result.doc.id}`);
			isOpen = false;
			query = '';
			dispatch('select', result);
		}
	}

	function handleCategoryChange() {
		if (query.length >= 2) {
			performSearch();
		}
	}

	function clearSearch() {
		query = '';
		results = [];
		inputElement?.focus();
	}
</script>

<div class="search-container relative">
	<div class="flex gap-2">
		<!-- Category filter -->
		{#if showCategoryFilter}
			<select
				bind:value={category}
				on:change={handleCategoryChange}
				class="w-auto min-w-[120px] rounded-md border border-[#2b3655] bg-[#18243b] px-3 py-2 text-sm text-[#d8ddf4] focus:border-[#7f88c4] focus:outline-none"
			>
				<option value="">All Categories</option>
				{#each categories.filter(c => c !== '') as cat}
					<option value={cat}>{CATEGORY_CONFIG[cat].title}</option>
				{/each}
			</select>
		{/if}

		<!-- Search input -->
		<div class="relative flex-1">
			<input
				bind:this={inputElement}
				bind:value={query}
				on:focus={handleFocus}
				on:blur={handleBlur}
				on:keydown={handleKeydown}
				type="search"
				{placeholder}
				aria-label="Search all Radar evidence"
				class="w-full rounded-full border border-[#2b3655] bg-[#18243b] px-4 py-2 pr-10 text-sm text-[#d8ddf4] placeholder:text-[#7d86a8] focus:border-[#7f88c4] focus:outline-none"
			/>

			{#if query}
				<button
					on:click={clearSearch}
					class="absolute right-3 top-1/2 -translate-y-1/2 text-trend-gray-400 hover:text-trend-gray-600"
					aria-label="Clear search"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="w-5 h-5"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			{:else}
				<span class="absolute right-3 top-1/2 -translate-y-1/2 text-trend-gray-400">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="w-5 h-5"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
						/>
					</svg>
				</span>
			{/if}
		</div>
	</div>

	<!-- Results dropdown -->
	{#if isOpen && results.length > 0}
		<SearchResults
			{results}
			{selectedIndex}
			on:select={(e) => selectResult(e.detail)}
		/>
	{:else if isOpen && query.length >= 2 && results.length === 0}
		<div class="absolute z-[60] mt-2 w-full rounded-xl border border-[#2b3655] bg-[#111d33] p-4 shadow-2xl">
			<p class="text-center text-sm text-[#b2b8cf]" aria-live="polite">
				{#if isLoading}
					Loading the search index…
				{:else if initializationFailed}
					Search is temporarily unavailable. Please try again.
				{:else if !isReady}
					Loading the search index…
				{:else}
					No results found for "{query}"
				{/if}
			</p>
		</div>
	{/if}
</div>

<script lang="ts">
    import { onMount } from 'svelte';
    
    interface Tool {
        name: string;
        description: string;
        url: string;
        category: string;
    }

    let tools: Tool[] = [];
    let loading = true;
    let searchQuery = '';
    let selectedCategory = 'All';
    let categories: string[] = ['All'];

    onMount(async () => {
        try {
            const res = await fetch('/data/tools.json');
            if (res.ok) {
                tools = await res.json();
                const cats = new Set(tools.map(t => t.category));
                categories = ['All', ...Array.from(cats).sort()];
            }
        } catch (e) {
            console.error('Failed to load tools:', e);
        } finally {
            loading = false;
        }
    });

    $: filteredTools = tools.filter(tool => {
        const matchesSearch = tool.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                              tool.description.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesCategory = selectedCategory === 'All' || tool.category === selectedCategory;
        return matchesSearch && matchesCategory;
    });
</script>

<svelte:head>
    <title>AI Tools Directory | AI Observatory</title>
</svelte:head>

<div class="max-w-[1600px] mx-auto py-4">
    <div class="mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">AI Tools Directory</h1>
        <p class="text-[#b2b8cf] text-base max-w-3xl">A browsable map of the AI stack — open-source libraries and commercial/enterprise platforms alike, grouped by category.</p>
    </div>

    <!-- Filters & Search -->
    <div class="flex flex-col lg:flex-row gap-4 mb-8">
        <div class="relative w-full lg:w-96 shrink-0">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#8e94ae] pointer-events-none">search</span>
            <input 
                type="text" 
                bind:value={searchQuery}
                placeholder="Search tools by name or description..." 
                class="w-full bg-[#1b2437] border border-[#2b3655] rounded-lg pl-10 pr-4 py-2.5 text-[#cfd5ff] placeholder-[#8e94ae] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
            />
        </div>
        
        <div class="flex flex-wrap gap-2">
            {#each categories as category}
                <button 
                    on:click={() => selectedCategory = category}
                    class="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 {selectedCategory === category ? 'bg-[#9aa6ff] text-[#0b1426] shadow-[0_0_12px_rgba(154,166,255,0.3)]' : 'bg-[#1b2437] text-[#b2b8cf] hover:bg-[#232a3a] hover:text-[#d8ddf4] border border-[#2b3655]'}"
                >
                    {category}
                </button>
            {/each}
        </div>
    </div>

    <!-- Grid -->
    {#if loading}
        <div class="flex justify-center py-20">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#9aa6ff]"></div>
        </div>
    {:else if filteredTools.length === 0}
        <div class="text-center py-20 bg-[#111d33]/50 rounded-xl border border-[#2b3655]">
            <span class="material-symbols-outlined text-5xl text-[#8e94ae] mb-4 block">search_off</span>
            <h3 class="text-xl font-medium text-white mb-2">No tools found</h3>
            <p class="text-[#b2b8cf]">Try adjusting your search query or category filter.</p>
            <button 
                on:click={() => { searchQuery = ''; selectedCategory = 'All'; }}
                class="mt-6 px-5 py-2.5 bg-[#1b2437] text-[#cfd5ff] font-medium rounded-lg hover:bg-[#232a3a] hover:text-white transition-colors border border-[#2b3655]"
            >
                Clear Filters
            </button>
        </div>
    {:else}
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
            {#each filteredTools as tool}
                <a 
                    href={tool.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    class="flex flex-col bg-[#0c1322] border border-[#2b3655] rounded-xl p-5 hover:border-[#9aa6ff] hover:-translate-y-1 hover:shadow-[0_8px_24px_-12px_rgba(154,166,255,0.3)] hover:bg-[#111d33] transition-all duration-300 group"
                >
                    <div class="flex items-start justify-between mb-3">
                        <h3 class="text-[17px] font-semibold tracking-wide text-white group-hover:text-[#9aa6ff] transition-colors line-clamp-1">{tool.name}</h3>
                        <span class="material-symbols-outlined text-[#8e94ae] text-sm group-hover:text-[#9aa6ff] transition-colors opacity-0 group-hover:opacity-100">open_in_new</span>
                    </div>
                    <span class="inline-block px-2.5 py-1 bg-[#1b2437] text-[#9aa6ff] text-[11px] font-medium uppercase tracking-wider rounded mb-3 w-fit border border-[#2b3655]/50">{tool.category}</span>
                    <p class="text-[#8e94ae] text-[13px] leading-[1.6] line-clamp-4 mt-auto group-hover:text-[#b2b8cf] transition-colors">{tool.description}</p>
                </a>
            {/each}
        </div>
    {/if}
</div>

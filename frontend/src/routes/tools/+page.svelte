<script lang="ts">
    import { onMount } from 'svelte';
    
    interface Tool {
        name: string;
        description: string;
        url: string;
        category: string;
        subcategory: string;
    }

    let tools: Tool[] = [];
    let loading = true;
    let searchQuery = '';
    let selectedCategory: string | null = null;
    let selectedSubcategory: string | null = null;

    let categories: { name: string, count: number }[] = [];
    let subcategories: { name: string, count: number }[] = [];

    onMount(async () => {
        try {
            const res = await fetch('/data/tools.json?v=' + Date.now());
            if (res.ok) {
                tools = await res.json();
            }
        } catch (e) {
            console.error('Failed to load tools:', e);
        } finally {
            loading = false;
        }
    });

    $: searchLower = searchQuery.toLowerCase();
    
    // Filter globally based on search query
    $: allFilteredTools = tools.filter(t => 
        searchLower === '' || 
        t.name.toLowerCase().includes(searchLower) || 
        t.description.toLowerCase().includes(searchLower)
    );

    // Compute visible categories based on allFilteredTools
    $: {
        const catMap = new Map<string, number>();
        allFilteredTools.forEach(t => {
            const cat = t.category || 'General';
            catMap.set(cat, (catMap.get(cat) || 0) + 1);
        });
        categories = Array.from(catMap.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
        
        // Auto-select first category if current is invalid
        if (categories.length > 0 && (!selectedCategory || !categories.find(c => c.name === selectedCategory))) {
            selectedCategory = categories[0].name;
        } else if (categories.length === 0) {
            selectedCategory = null;
        }
    }

    // Compute visible subcategories based on allFilteredTools & selectedCategory
    $: {
        if (selectedCategory) {
            const catTools = allFilteredTools.filter(t => (t.category || 'General') === selectedCategory);
            const subMap = new Map<string, number>();
            catTools.forEach(t => {
                const sub = t.subcategory || 'General';
                subMap.set(sub, (subMap.get(sub) || 0) + 1);
            });
            subcategories = Array.from(subMap.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
            
            // Auto-select first subcategory
            if (subcategories.length > 0 && (!selectedSubcategory || !subcategories.find(s => s.name === selectedSubcategory))) {
                selectedSubcategory = subcategories[0].name;
            } else if (subcategories.length === 0) {
                selectedSubcategory = null;
            }
        } else {
            subcategories = [];
            selectedSubcategory = null;
        }
    }

    // Final tools to render in Col 3
    $: visibleTools = allFilteredTools.filter(t => (t.category || 'General') === selectedCategory && (t.subcategory || 'General') === selectedSubcategory);

    function getLogoUrl(url: string) {
        try {
            const parsedUrl = new URL(url);
            if (parsedUrl.hostname === 'github.com') {
                const parts = parsedUrl.pathname.split('/').filter(Boolean);
                if (parts.length >= 1) {
                    return `https://unavatar.io/github/${parts[0]}`;
                }
            }
            return `https://unavatar.io/${parsedUrl.hostname}`;
        } catch (e) {
            return `https://unavatar.io/example.com`;
        }
    }

    function handleImageError(event: Event) {
        const target = event.target as HTMLImageElement;
        target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%238e94ae"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>';
    }
</script>

<svelte:head>
    <title>AI Tools Directory | AI Observatory</title>
</svelte:head>

<div class="h-[calc(100vh-6rem)] max-w-[1800px] mx-auto p-4 md:p-6 flex flex-col">
    <div class="mb-6 shrink-0 flex flex-col md:flex-row gap-6 md:items-end justify-between">
        <div>
            <h1 class="text-3xl font-bold text-white mb-2">AI Tools Directory</h1>
            <p class="text-[#b2b8cf] text-base">A browsable map of the AI stack — open-source libraries and commercial platforms, updated daily.</p>
        </div>
        <div class="relative w-full md:w-96">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 text-[#8e94ae] w-5 h-5 pointer-events-none" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input 
                type="text" 
                bind:value={searchQuery}
                placeholder="Filter tools — name or what it does..." 
                class="w-full bg-[#1b2437] border border-[#2b3655] rounded-lg pl-10 pr-4 py-2.5 text-[#cfd5ff] placeholder-[#8e94ae] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all shadow-inner"
            />
        </div>
    </div>

    <!-- Miller Columns Layout -->
    <div class="flex-1 flex min-h-0 overflow-hidden bg-[#0c1322] border border-[#2b3655] rounded-xl shadow-2xl">
        {#if loading}
            <div class="w-full h-full flex items-center justify-center">
                <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#9aa6ff]"></div>
            </div>
        {:else if allFilteredTools.length === 0}
            <div class="w-full h-full flex flex-col items-center justify-center p-8 text-center bg-[#111d33]/30">
                <span class="material-symbols-outlined text-5xl text-[#8e94ae] mb-4 block">search_off</span>
                <h3 class="text-xl font-medium text-white mb-2">No tools found</h3>
                <p class="text-[#b2b8cf]">Try adjusting your search query.</p>
                <button 
                    on:click={() => searchQuery = ''}
                    class="mt-6 px-5 py-2.5 bg-[#1b2437] text-[#cfd5ff] font-medium rounded-lg hover:bg-[#232a3a] hover:text-white transition-colors border border-[#2b3655]"
                >
                    Clear Search
                </button>
            </div>
        {:else}
            <!-- Column 1: Categories -->
            <div class="w-64 md:w-72 lg:w-80 shrink-0 flex flex-col border-r border-[#2b3655] bg-[#0c1322]">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/50 shrink-0">
                    <h2 class="text-sm font-bold text-white uppercase tracking-wider flex items-center justify-between">
                        Categories 
                        <span class="bg-[#1b2437] border border-[#2b3655] text-[#cfd5ff] px-2 py-0.5 rounded-md text-xs">{categories.length}</span>
                    </h2>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-1">
                    {#each categories as category}
                        <button 
                            on:click={() => selectedCategory = category.name}
                            class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 {selectedCategory === category.name ? 'bg-gradient-to-r from-[#9aa6ff]/20 to-[#9aa6ff]/5 text-[#9aa6ff] shadow-[inset_2px_0_0_0_#9aa6ff]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-white'}"
                        >
                            <span class="truncate">{category.name}</span>
                            <span class="text-[11px] {selectedCategory === category.name ? 'bg-[#9aa6ff]/20 text-[#9aa6ff]' : 'bg-[#1b2437] text-[#8e94ae]'} px-2 py-0.5 rounded-full ml-2">{category.count}</span>
                        </button>
                    {/each}
                </div>
            </div>

            <!-- Column 2: Subcategories -->
            <div class="w-64 md:w-72 lg:w-80 shrink-0 flex flex-col border-r border-[#2b3655] bg-[#0c1322]">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/50 shrink-0">
                    <h2 class="text-sm font-bold text-white truncate max-w-[250px]" title={selectedCategory || ''}>
                        {selectedCategory || 'Subcategories'}
                    </h2>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-1">
                    {#each subcategories as subcategory}
                        <button 
                            on:click={() => selectedSubcategory = subcategory.name}
                            class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 {selectedSubcategory === subcategory.name ? 'bg-gradient-to-r from-[#00e0bb]/20 to-[#00e0bb]/5 text-[#00e0bb] shadow-[inset_2px_0_0_0_#00e0bb]' : 'text-[#b2b8cf] hover:bg-[#1b2437] hover:text-white'}"
                        >
                            <span class="truncate">{subcategory.name}</span>
                            <span class="text-[11px] {selectedSubcategory === subcategory.name ? 'bg-[#00e0bb]/20 text-[#00e0bb]' : 'bg-[#1b2437] text-[#8e94ae]'} px-2 py-0.5 rounded-full ml-2">{subcategory.count}</span>
                        </button>
                    {/each}
                </div>
            </div>

            <!-- Column 3: Tools -->
            <div class="flex-1 flex flex-col bg-[#0b1426]/80">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md shrink-0 flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-bold text-white">{selectedSubcategory || 'Tools'}</h2>
                        <p class="text-[13px] text-[#8e94ae] mt-0.5">{selectedCategory} • {visibleTools.length} tools</p>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-3">
                    {#each visibleTools as tool}
                        <a 
                            href={tool.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            class="flex items-start gap-4 p-4 rounded-xl bg-[#0c1322] border border-[#2b3655] hover:border-[#9aa6ff] hover:bg-[#111d33] hover:shadow-lg transition-all duration-200 group"
                        >
                            <div class="w-[52px] h-[52px] shrink-0 bg-[#1b2437] rounded-lg flex items-center justify-center overflow-hidden border border-[#2b3655] shadow-inner">
                                <img src={getLogoUrl(tool.url)} alt={tool.name} loading="lazy" decoding="async" class="w-full h-full object-cover bg-white" on:error={handleImageError} />
                            </div>
                            <div class="flex-1 min-w-0 pt-0.5">
                                <div class="flex justify-between items-start mb-1">
                                    <h3 class="text-base font-semibold text-white group-hover:text-[#9aa6ff] transition-colors truncate pr-4">{tool.name}</h3>
                                    <span class="material-symbols-outlined text-[#8e94ae] text-[18px] group-hover:text-[#9aa6ff] transition-colors opacity-0 group-hover:opacity-100">open_in_new</span>
                                </div>
                                <p class="text-[13.5px] text-[#b2b8cf] leading-relaxed line-clamp-2">{tool.description}</p>
                            </div>
                        </a>
                    {/each}
                </div>
            </div>
        {/if}
    </div>
</div>

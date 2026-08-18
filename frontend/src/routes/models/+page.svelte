<script lang="ts">
    import { onMount } from 'svelte';
    import { fade, slide } from 'svelte/transition';
    import { slugify } from '$lib/utils/slugify';
    import SuggestModelModal from '$lib/components/SuggestModelModal.svelte';
    import PageMeta from '$lib/components/seo/PageMeta.svelte';
    import { absoluteUrl } from '$lib/config/site';

    interface Model {
        name: string;
        description: string;
        url: string;
        category: string; // Maker
        subcategory: string; // Family
    }

    let models: Model[] = [];
    let loading = true;
    let searchQuery = '';
    let selectedCategory: string | null = null;
    let selectedSubcategory: string | null = null;
    
    let isModalOpen = false;

    onMount(async () => {
        try {
            const res = await fetch('/data/models.json?v=' + Date.now());
            if (res.ok) {
                models = await res.json();
            }
        } catch (e) {
            console.error('Failed to load models:', e);
        } finally {
            loading = false;
        }
    });

    $: searchLower = searchQuery.toLowerCase().trim();
    
    let previousSearch = '';
    $: if (searchLower !== previousSearch) {
        selectedCategory = null;
        selectedSubcategory = null;
        previousSearch = searchLower;
    }
    
    // Filter globally based on search query
    $: allFilteredModels = models.filter(t => 
        searchLower === '' || 
        t.name.toLowerCase().includes(searchLower) || 
        t.description.toLowerCase().includes(searchLower)
    );

    let categories: { name: string, count: number }[] = [];
    let subcategories: { name: string, count: number }[] = [];
    const catMap = new Map<string, number>();

    // Compute category counts based on search
    $: {
        catMap.clear();
        allFilteredModels.forEach(t => {
            const cat = t.category || 'Other';
            catMap.set(cat, (catMap.get(cat) || 0) + 1);
        });
        categories = Array.from(catMap.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
        
        // Auto-select first category if current is invalid (only when not searching)
        if (searchLower === '') {
            if (categories.length > 0 && (!selectedCategory || !categories.find(c => c.name === selectedCategory))) {
                selectedCategory = categories[0].name;
            } else if (categories.length === 0) {
                selectedCategory = null;
            }
        } else {
            // When searching, if the selected category is no longer valid, clear it
            if (selectedCategory && !categories.find(c => c.name === selectedCategory)) {
                selectedCategory = null;
            }
        }
    }

    // Compute visible subcategories based on allFilteredModels & selectedCategory
    $: {
        if (selectedCategory) {
            const catModels = allFilteredModels.filter(t => (t.category || 'Other') === selectedCategory);
            const subMap = new Map<string, number>();
            catModels.forEach(t => {
                const sub = t.subcategory || 'Other';
                subMap.set(sub, (subMap.get(sub) || 0) + 1);
            });
            subcategories = Array.from(subMap.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
            
            // Auto-select first subcategory (only if a category is strictly selected)
            if (searchLower === '' || selectedCategory) {
                if (subcategories.length > 0 && (!selectedSubcategory || !subcategories.find(s => s.name === selectedSubcategory))) {
                    selectedSubcategory = subcategories[0].name;
                } else if (subcategories.length === 0) {
                    selectedSubcategory = null;
                }
            }
        } else {
            subcategories = [];
            selectedSubcategory = null;
        }
    }

    // Final models to render in Col 3
    $: visibleModels = allFilteredModels.filter(t => 
        (!selectedCategory || (t.category || 'Other') === selectedCategory) && 
        (!selectedSubcategory || (t.subcategory || 'Other') === selectedSubcategory)
    );

    const domainMap: Record<string, string> = {
        'Anthropic': 'anthropic.com',
        'OpenAI': 'openai.com',
        'Google': 'google.com',
        'Meta': 'meta.com',
        'DeepSeek': 'deepseek.com',
        'Alibaba (Qwen)': 'alibabagroup.com',
        'Moonshot AI (Kimi)': 'moonshot.cn',
        'Z.ai (Zhipu / GLM)': 'zhipuai.cn',
        'xAI (Grok)': 'x.ai',
        'Mistral AI': 'mistral.ai',
        'Cohere': 'cohere.com',
        'MiniMax': 'minimaxi.com',
        'ByteDance': 'bytedance.com',
        'Tencent': 'tencent.com',
        'Thinking Machines Lab': 'thinkingmachines.com'
    };

    function getLogoUrl(model: Model) {
        if (model.category && domainMap[model.category]) {
            const domain = domainMap[model.category];
            const safe = domain.replace(/\./g, '_').replace(/:/g, '_').replace(/\//g, '_');
            return `/icons/${safe}.png`;
        }
        return `/icons/example_com.png`;
    }

    function handleImageError(event: Event) {
        const target = event.target as HTMLImageElement;
        // Try SVG fallback (letter icon)
        if (target.src.endsWith('.png')) {
            target.src = target.src.replace('.png', '.svg');
        } else {
            target.style.display = 'none';
        }
    }
</script>

<PageMeta title="AI Models Directory" description="A browsable registry of large language models — frontier and open-weight — with verified specs, benchmarks, pricing and APIs." path="/models" />
<svelte:head>
    {@html `
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "AI Models Directory",
        "description": "A browsable registry of large language models — frontier and open-weight — with verified specs, benchmarks, pricing and APIs.",
        "url": "${absoluteUrl('/models')}"
    }
    </script>
    `}
</svelte:head>

<div class="h-[calc(100vh-6rem)] max-w-[1800px] mx-auto p-4 md:p-6 flex flex-col">
    <div class="mb-6 shrink-0 flex flex-col md:flex-row gap-6 md:items-end justify-between">
        <div class="max-w-3xl">
            <h1 class="text-3xl font-bold text-white mb-2">AI Models Directory</h1>
            <p class="text-[#b2b8cf] text-base">A browsable registry of large language models — frontier and open-weight — with verified specs, benchmarks, pricing and APIs. Filter by maker, family and capability.</p>
        </div>
        <div class="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
            <div class="relative w-full md:w-80">
                <svg class="absolute left-3 top-1/2 -translate-y-1/2 text-[#8e94ae] w-5 h-5 pointer-events-none" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input 
                    type="text" 
                    bind:value={searchQuery}
                    placeholder="Filter models..." 
                    class="w-full bg-[#1b2437] border border-[#2b3655] rounded-lg pl-10 pr-4 py-2.5 text-[#cfd5ff] placeholder-[#8e94ae] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all shadow-inner"
                />
            </div>
            <button 
                on:click={() => isModalOpen = true}
                class="px-4 py-2.5 bg-[#9aa6ff] text-[#0c1322] font-semibold rounded-lg hover:bg-[#8694ff] transition-colors flex items-center justify-center gap-2 whitespace-nowrap shrink-0"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                Suggest Model
            </button>
        </div>
    </div>

    <!-- Miller Columns Layout -->
    <div class="flex-1 flex min-h-0 overflow-hidden bg-[#0c1322] border border-[#2b3655] rounded-xl shadow-2xl">
        {#if loading}
            <div class="w-full h-full flex items-center justify-center">
                <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#9aa6ff]"></div>
            </div>
        {:else if allFilteredModels.length === 0}
            <div class="w-full h-full flex flex-col items-center justify-center p-8 text-center bg-[#111d33]/30">
                <span class="material-symbols-outlined text-5xl text-[#8e94ae] mb-4 block">search_off</span>
                <h3 class="text-xl font-medium text-white mb-2">No models found</h3>
                <p class="text-[#b2b8cf]">Try adjusting your search query.</p>
            </div>
        {:else}
            <!-- Column 1: Makers -->
            <div class="w-64 border-r border-[#2b3655] flex flex-col bg-[#0b1426]/50 shrink-0">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md shrink-0">
                    <h2 class="text-xs font-bold uppercase tracking-wider text-[#8e94ae]">Maker</h2>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-1">
                    {#each categories as cat}
                        <button 
                            class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg transition-all duration-200 text-left {selectedCategory === cat.name ? 'bg-[#9aa6ff]/10 text-[#cfd5ff] ring-1 ring-[#9aa6ff]/30 shadow-sm' : 'text-[#8e94ae] hover:bg-[#1b2437] hover:text-[#b2b8cf]'}"
                            on:click={() => selectedCategory = cat.name}
                        >
                            <span class="font-medium truncate pr-2 text-[14px]">{cat.name}</span>
                            <span class="text-[11px] px-1.5 py-0.5 rounded-md {selectedCategory === cat.name ? 'bg-[#9aa6ff]/20 text-[#cfd5ff]' : 'bg-[#1b2437] text-[#8e94ae]'}">{cat.count}</span>
                        </button>
                    {/each}
                </div>
            </div>

            <!-- Column 2: Families -->
            <div class="w-72 border-r border-[#2b3655] flex flex-col bg-[#0c1322] shrink-0">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md shrink-0">
                    <h2 class="text-xs font-bold uppercase tracking-wider text-[#8e94ae]">Family</h2>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-1">
                    {#if subcategories.length === 0}
                        <div class="p-4 text-sm text-[#8e94ae] text-center italic">Select a maker</div>
                    {:else}
                        {#each subcategories as sub}
                            <button 
                                class="w-full flex items-center justify-between px-3 py-2 rounded-lg transition-all duration-200 text-left {selectedSubcategory === sub.name ? 'bg-[#1b2437] text-white shadow-[inset_2px_0_0_0_#9aa6ff]' : 'text-[#8e94ae] hover:bg-[#111d33] hover:text-[#b2b8cf]'}"
                                on:click={() => selectedSubcategory = sub.name}
                            >
                                <span class="text-[13px] truncate pr-2">{sub.name}</span>
                                <span class="text-[11px] px-1.5 py-0.5 rounded text-[#8e94ae] {selectedSubcategory === sub.name ? 'bg-[#2b3655]' : ''}">{sub.count}</span>
                            </button>
                        {/each}
                    {/if}
                </div>
            </div>

            <!-- Column 3: Models -->
            <div class="flex-1 flex flex-col bg-[#0b1426]/80">
                <div class="p-4 border-b border-[#2b3655] bg-[#111d33]/80 backdrop-blur-md shrink-0 flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-bold text-white">{selectedSubcategory || (searchLower ? 'Search Results' : 'Models')}</h2>
                        <p class="text-[13px] text-[#8e94ae] mt-0.5">{selectedCategory || (searchLower ? 'All Makers' : '')} {#if selectedCategory}•{/if} {visibleModels.length} models</p>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-3">
                    {#each visibleModels as tool}
                        <a 
                            href="/models/{slugify(tool.name)}" 
                            class="flex items-start gap-4 p-4 rounded-xl bg-[#0c1322] border border-[#2b3655] hover:border-[#9aa6ff] hover:bg-[#111d33] hover:shadow-lg transition-all duration-200 group"
                        >
                            <div class="w-[52px] h-[52px] shrink-0 bg-[#1b2437] rounded-lg flex items-center justify-center overflow-hidden border border-[#2b3655] shadow-inner p-1">
                                <img src={getLogoUrl(tool)} alt={tool.name} loading="lazy" decoding="async" class="w-full h-full object-contain rounded" on:error={handleImageError} />
                            </div>
                            <div class="flex-1 min-w-0 pt-0.5">
                                <div class="flex justify-between items-start mb-1">
                                    <h3 class="text-base font-semibold text-white group-hover:text-[#9aa6ff] transition-colors truncate pr-4">{tool.name}</h3>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-[#8e94ae] group-hover:text-[#9aa6ff] transition-colors opacity-0 group-hover:opacity-100 mt-0.5"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
                                </div>
                                <p class="text-[13.5px] text-[#b2b8cf] leading-relaxed">{tool.description}</p>
                            </div>
                        </a>
                    {/each}
                </div>
            </div>
        {/if}
    </div>
</div>

<SuggestModelModal bind:isOpen={isModalOpen} />

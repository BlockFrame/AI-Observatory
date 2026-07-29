<script lang="ts">
    import { page } from '$app/stores';
    import { onMount } from 'svelte';
    import { slugify } from '$lib/utils/slugify';

    interface Model {
        name: string;
        description: string;
        url: string;
        category: string; // Maker
        subcategory: string; // Family
    }

    let loading = true;
    let model: Model | null = null;
    let error: string | null = null;

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

    function getLogoUrl(m: Model) {
        if (m.category && domainMap[m.category]) {
            const domain = domainMap[m.category];
            const safe = domain.replace(/\./g, '_').replace(/:/g, '_').replace(/\//g, '_');
            return `/icons/${safe}.png`;
        }
        return `/icons/example_com.png`;
    }

    function handleImageError(event: Event) {
        const target = event.target as HTMLImageElement;
        if (target.src.endsWith('.png')) {
            target.src = target.src.replace('.png', '.svg');
        } else {
            target.style.display = 'none';
        }
    }

    onMount(async () => {
        try {
            const slug = $page.params.slug;
            const res = await fetch('/data/models.json?v=' + Date.now());
            if (res.ok) {
                const allModels: Model[] = await res.json();
                model = allModels.find(m => slugify(m.name) === slug) || null;
                if (!model) {
                    error = 'Modello non trovato.';
                }
            } else {
                error = 'Errore nel caricamento dei dati.';
            }
        } catch (e) {
            console.error('Failed to load model:', e);
            error = 'Errore di connessione.';
        } finally {
            loading = false;
        }
    });
</script>

<svelte:head>
    {#if model}
        <title>{model.name} | AI Observatory</title>
        <meta name="description" content={model.description} />
    {:else}
        <title>Loading... | AI Observatory</title>
    {/if}
</svelte:head>

<div class="h-full min-h-[calc(100vh-6rem)] max-w-4xl mx-auto p-4 md:p-8">
    <a href="/models" class="inline-flex items-center gap-2 text-[#8e94ae] hover:text-[#9aa6ff] mb-8 transition-colors group">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="group-hover:-translate-x-1 transition-transform"><path d="m15 18-6-6 6-6"/></svg>
        <span class="font-medium">Back to Models Directory</span>
    </a>

    {#if loading}
        <div class="flex items-center justify-center h-64">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#9aa6ff]"></div>
        </div>
    {:else if error || !model}
        <div class="flex flex-col items-center justify-center p-12 text-center bg-[#0c1322] border border-[#2b3655] rounded-xl shadow-2xl">
            <span class="material-symbols-outlined text-6xl text-[#8e94ae] mb-4 block">error_outline</span>
            <h1 class="text-2xl font-bold text-white mb-2">Model Not Found</h1>
            <p class="text-[#b2b8cf] mb-6">{error || 'The model you are looking for does not exist or has been removed.'}</p>
            <a href="/models" class="px-6 py-2.5 bg-[#1b2437] hover:bg-[#2b3655] text-white rounded-lg transition-colors border border-[#2b3655]">Return to Directory</a>
        </div>
    {:else}
        <article class="bg-[#0c1322] border border-[#2b3655] rounded-2xl p-6 md:p-10 shadow-2xl relative overflow-hidden">
            <!-- Background glow -->
            <div class="absolute -top-32 -right-32 w-96 h-96 bg-[#9aa6ff]/5 rounded-full blur-[100px] pointer-events-none"></div>

            <div class="relative z-10 flex flex-col md:flex-row gap-6 md:gap-10 items-start">
                <div class="w-24 h-24 shrink-0 bg-[#1b2437] rounded-xl flex items-center justify-center overflow-hidden border border-[#2b3655] shadow-inner p-2">
                    <img src={getLogoUrl(model)} alt={model.name} loading="eager" class="w-full h-full object-contain rounded" on:error={handleImageError} />
                </div>
                
                <div class="flex-1">
                    <div class="flex flex-col sm:flex-row sm:items-center gap-4 justify-between mb-4">
                        <h1 class="text-3xl font-bold text-white tracking-tight">{model.name}</h1>
                        <a 
                            href={model.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            class="inline-flex items-center gap-2 px-5 py-2.5 bg-[#9aa6ff] hover:bg-[#b0bcff] text-[#0b1426] font-semibold rounded-lg transition-colors shadow-[0_0_15px_rgba(154,166,255,0.2)] whitespace-nowrap"
                        >
                            <span>Visita il sito ufficiale</span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
                        </a>
                    </div>
                    
                    <div class="flex flex-wrap gap-3 mb-6">
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-[#111d33] border border-[#2b3655] rounded-md text-sm text-[#8e94ae] font-medium">
                            <span class="material-symbols-outlined text-[16px]">business</span>
                            Maker: {model.category || 'Unknown'}
                        </span>
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-[#111d33] border border-[#2b3655] rounded-md text-sm text-[#8e94ae] font-medium">
                            <span class="material-symbols-outlined text-[16px]">account_tree</span>
                            Family: {model.subcategory || 'Unknown'}
                        </span>
                    </div>

                    <div class="prose prose-invert prose-p:text-[#b2b8cf] prose-p:leading-relaxed max-w-none">
                        <h3 class="text-lg font-semibold text-white mb-3 mt-8 border-b border-[#2b3655] pb-2">Descrizione</h3>
                        <p class="text-base">{model.description}</p>
                    </div>
                </div>
            </div>
        </article>
    {/if}
</div>

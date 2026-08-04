<script lang="ts">
    import { page } from '$app/stores';
    import { onMount } from 'svelte';
    import { slugify } from '$lib/utils/slugify';
    import { safeHtml } from '$lib/services/safeHtml';

    // We now receive data directly from +page.server.ts load function
    export let data: any;

    let { model, htmlContent } = data;
    
    // We keep these in case client-side navigation needs it (though it shouldn't if prerendered properly, but good fallback)
    let loading = !model;
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

    function getLogoUrl(m: any) {
        if (m && m.category && domainMap[m.category]) {
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
        // If data wasn't provided via SSR (e.g. CSR navigation without data payload), fallback to fetching
        if (!model) {
            try {
                const slug = $page.params.slug;
                const res = await fetch('/data/models.json?v=' + Date.now());
                if (res.ok) {
                    const allModels = await res.json();
                    model = allModels.find((m: any) => slugify(m.name) === slug) || null;
                    if (!model) {
                        error = 'Modello non trovato.';
                    } else {
                        // Also try to fetch content client-side
                        const cRes = await fetch('/data/models-content.json');
                        if (cRes.ok && slug) {
                            const cMap = await cRes.json();
                            htmlContent = cMap[slug] || null;
                        }
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
        }
    });
</script>

<svelte:head>
    {#if model}
        <title>{model.name} | AI Models Directory</title>
        <meta name="description" content={model.description} />
        
        <meta property="og:type" content="article" />
        <meta property="og:title" content="{model.name} | AI Models Directory" />
        <meta property="og:description" content={model.description} />
        <meta property="og:url" content={`https://ai-observatory.vercel.app/models/${$page.params.slug}`} />
        
        <meta name="twitter:card" content="summary" />
        <meta name="twitter:title" content="{model.name} | AI Models Directory" />
        <meta name="twitter:description" content={model.description} />
        
        {@html `
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "${model.name.replace(/"/g, '\\"')}",
            "description": "${model.description.replace(/"/g, '\\"')}",
            "applicationCategory": "DeveloperApplication",
            "operatingSystem": "Any",
            "developer": {
                "@type": "Organization",
                "name": "${(model.category || 'Unknown').replace(/"/g, '\\"')}"
            },
            "url": "https://ai-observatory.vercel.app/models/${$page.params.slug}"
        }
        </script>
        `}
    {:else}
        <title>Loading... | AI Observatory</title>
    {/if}
</svelte:head>

<div class="h-full min-h-[calc(100vh-6rem)] max-w-[1100px] mx-auto p-4 md:p-8 pb-20">
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
        <!-- Hero Header -->
        <header class="flex flex-col md:flex-row gap-6 md:gap-8 items-start mb-12 border-b border-[#2b3655] pb-10">
            <div class="w-24 h-24 shrink-0 bg-[#1b2437] rounded-xl flex items-center justify-center overflow-hidden border border-[#2b3655] shadow-[0_0_20px_rgba(43,54,85,0.4)] p-2">
                <img src={getLogoUrl(model)} alt={model.name} loading="eager" class="w-full h-full object-contain rounded" on:error={handleImageError} />
            </div>
            
            <div class="flex-1 pt-1">
                <h1 class="text-4xl md:text-5xl font-black text-white tracking-tight mb-4">{model.name}</h1>
                <div class="flex flex-wrap gap-3 mb-4">
                    <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-[#111d33] border border-[#2b3655] rounded-md text-sm text-[#8e94ae] font-medium">
                        <span class="material-symbols-outlined text-[16px]">business</span>
                        Maker: {model.category || 'Unknown'}
                    </span>
                    <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-[#111d33] border border-[#2b3655] rounded-md text-sm text-[#8e94ae] font-medium">
                        <span class="material-symbols-outlined text-[16px]">account_tree</span>
                        Family: {model.subcategory || 'Unknown'}
                    </span>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="model-content-wrapper relative">
            {#if htmlContent}
                <!-- Inject the scraped HTML directly -->
                <div class="scraped-content prose prose-invert prose-p:text-[#b2b8cf] prose-p:leading-relaxed prose-headings:text-white prose-a:text-[#9aa6ff] prose-a:no-underline hover:prose-a:underline prose-code:text-[#9aa6ff] prose-code:bg-[#111d33] prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-[#0c1322] prose-pre:border prose-pre:border-[#2b3655] max-w-none">
                    {@html safeHtml(htmlContent)}
                </div>
            {:else}
                <div class="prose prose-invert prose-p:text-[#b2b8cf] prose-p:leading-relaxed max-w-none bg-[#0c1322] p-8 rounded-2xl border border-[#2b3655]">
                    <h3 class="text-xl font-semibold text-white mb-4">Descrizione</h3>
                    <p class="text-lg">{model.description}</p>
                    
                    <div class="mt-8 p-4 bg-[#111d33] border border-[#2b3655] rounded-lg flex items-start gap-3">
                        <span class="material-symbols-outlined text-[#8e94ae]">info</span>
                        <p class="text-sm text-[#8e94ae] m-0">Nessun contenuto dettagliato trovato per questo modello.</p>
                    </div>
                </div>
            {/if}
        </main>
    {/if}
</div>

<style>
    /* 
     * Custom styles to format the injected ai-tldr.dev HTML.
     * We override their brutalist style to match our dark premium aesthetic.
     */
    :global(.scraped-content .lrn-section) {
        margin-bottom: 3rem;
    }
    :global(.scraped-content .lrn-h2) {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #2b3655;
        padding-bottom: 0.75rem;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    :global(.scraped-content .lrn-h2-mark) {
        color: #9aa6ff;
        font-weight: 400;
        opacity: 0.7;
    }
    :global(.scraped-content .lrn-h3) {
        font-size: 1.25rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        color: #e2e8f0;
    }
    :global(.scraped-content .lrn-list) {
        list-style-type: disc;
        padding-left: 1.5rem;
        color: #b2b8cf;
    }
    :global(.scraped-content .lrn-list li) {
        margin-bottom: 0.5rem;
    }
    
    /* Tables */
    :global(.scraped-content .lrn-table-wrap) {
        overflow-x: auto;
        margin: 1.5rem 0;
        border: 1px solid #2b3655;
        border-radius: 0.75rem;
        background: #0c1322;
    }
    :global(.scraped-content .lrn-table) {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
    }
    :global(.scraped-content .lrn-table th) {
        background: #111d33;
        color: #8e94ae;
        font-weight: 600;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid #2b3655;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    :global(.scraped-content .lrn-table td) {
        padding: 1rem;
        border-bottom: 1px solid #2b3655;
        color: #b2b8cf;
    }
    :global(.scraped-content .lrn-table tr:last-child td) {
        border-bottom: none;
    }
    
    /* FAQ Details */
    :global(.scraped-content .lrn-faq-item) {
        margin-bottom: 1rem;
        border: 1px solid #2b3655;
        border-radius: 0.75rem;
        background: #0c1322;
        overflow: hidden;
    }
    :global(.scraped-content .lrn-faq-item summary) {
        padding: 1rem 1.25rem;
        font-weight: 600;
        color: #ffffff;
        cursor: pointer;
        background: #111d33;
        list-style: none; /* Hide default arrow in some browsers */
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    :global(.scraped-content .lrn-faq-item summary::-webkit-details-marker) {
        display: none;
    }
    :global(.scraped-content .lrn-faq-item summary::after) {
        content: '+';
        color: #9aa6ff;
        font-size: 1.25rem;
        line-height: 1;
    }
    :global(.scraped-content .lrn-faq-item[open] summary::after) {
        content: '−';
    }
    :global(.scraped-content .lrn-faq-item p) {
        padding: 1.25rem;
        margin: 0;
        border-top: 1px solid #2b3655;
    }
    
    /* Hide some elements we don't want */
    :global(.scraped-content .lrn-tool-aside),
    :global(.scraped-content .lrn-pn),
    :global(.scraped-content figure),
    :global(.scraped-content img) {
        display: none;
    }
</style>

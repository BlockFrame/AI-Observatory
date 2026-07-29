<script lang="ts">
    import { onMount } from 'svelte';
    export let data: any;
    let { htmlContent } = data;

    onMount(() => {
        // Open all links in the scraped content in a new tab
        const links = document.querySelectorAll('.scraped-content a');
        links.forEach(link => {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        });
    });
</script>

<svelte:head>
    <title>Top AI Influencers to Follow | AI Observatory</title>
    <meta name="description" content="116 AI people worth following, grouped by what they actually do." />
</svelte:head>

<div class="h-full min-h-[calc(100vh-6rem)] max-w-[1100px] mx-auto p-4 md:p-8 pb-20">
    <!-- Hero Header -->
    <header class="flex flex-col gap-4 items-start mb-12 border-b border-[#2b3655] pb-8">
        <h1 class="text-4xl md:text-5xl font-black text-white tracking-tight">AI Influencers</h1>
        <p class="text-xl text-[#8e94ae] max-w-2xl">
            The AI people worth following, grouped by what they actually do — frontier-lab founders, researchers, educators, engineers, tool creators, podcasts and newsletters.
        </p>
    </header>

    <!-- Main Content -->
    <main class="influencers-content-wrapper relative">
        {#if htmlContent}
            <!-- Inject the scraped HTML directly -->
            <div class="scraped-content prose prose-invert prose-p:text-[#b2b8cf] prose-p:leading-relaxed prose-headings:text-white prose-a:text-[#9aa6ff] prose-a:no-underline hover:prose-a:underline max-w-none">
                {@html htmlContent}
            </div>
        {:else}
            <div class="flex flex-col items-center justify-center p-12 text-center bg-[#0c1322] border border-[#2b3655] rounded-xl shadow-2xl">
                <span class="material-symbols-outlined text-6xl text-[#8e94ae] mb-4 block">error_outline</span>
                <h2 class="text-2xl font-bold text-white mb-2">Content Not Available</h2>
                <p class="text-[#b2b8cf] mb-6">Could not load the influencers list.</p>
            </div>
        {/if}
    </main>
</div>

<style>
    /* 
     * Custom styles to format the injected ai-tldr.dev HTML.
     */
    :global(.scraped-content nav.rls-crumbs),
    :global(.scraped-content h1),
    :global(.scraped-content p.rls-summary),
    :global(.scraped-content .rls-back) {
        /* Hide the original header elements since we built our own */
        display: none;
    }

    :global(.scraped-content section) {
        margin-bottom: 4rem;
    }
    
    :global(.scraped-content h2) {
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: 1px solid #2b3655;
        padding-bottom: 0.75rem;
    }
    
    :global(.scraped-content section > p) {
        color: #8e94ae;
        font-size: 1.125rem;
        margin-bottom: 2rem;
    }

    /* List styling */
    :global(.scraped-content ul.inf-x-list) {
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 1.5rem;
    }

    :global(.scraped-content ul.inf-x-list > li) {
        list-style: none !important;
        list-style-type: none !important;
        background: #0c1322;
        border: 1px solid #2b3655;
        border-radius: 0.75rem;
        padding: 1.5rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        display: flex;
        flex-direction: column;
    }

    /* Forcefully hide Tailwind prose bullet points */
    :global(.scraped-content ul.inf-x-list > li::marker),
    :global(.scraped-content ul.inf-x-list > li::before) {
        content: none !important;
        display: none !important;
    }

    :global(.scraped-content ul.inf-x-list > li:hover) {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        border-color: #3b4b75;
    }

    /* Name and handle */
    :global(.scraped-content ul.inf-x-list > li > a > strong) {
        font-size: 1.25rem;
        color: #ffffff;
        display: block;
        margin-bottom: 0.25rem;
    }
    
    :global(.scraped-content ul.inf-x-list > li > a) {
        text-decoration: none !important;
    }

    /* Meta info (e.g. @sama · Twitter/X · 1M+) */
    :global(.scraped-content .inf-x-meta) {
        display: block;
        font-size: 0.75rem;
        color: #8e94ae;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        font-weight: 600;
    }

    /* Description */
    :global(.scraped-content ul.inf-x-list > li > p:not(.rls-links)) {
        color: #b2b8cf;
        font-size: 0.9375rem;
        line-height: 1.6;
        flex-grow: 1;
        margin: 0 0 1.25rem 0;
    }

    /* Links container (Blog, GitHub, etc.) */
    :global(.scraped-content .rls-links) {
        margin: 0;
        padding-top: 1rem;
        border-top: 1px dashed #2b3655;
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        font-size: 0.875rem;
    }

    :global(.scraped-content .rls-links a) {
        display: inline-flex;
        align-items: center;
        color: #9aa6ff !important;
        background: #111d33;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        border: 1px solid #2b3655;
        transition: all 0.2s ease;
    }

    :global(.scraped-content .rls-links a:hover) {
        background: #9aa6ff;
        color: #0b1426 !important;
        border-color: #9aa6ff;
        text-decoration: none !important;
    }
</style>

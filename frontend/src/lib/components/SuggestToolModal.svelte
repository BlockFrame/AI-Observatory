<script>
    import { createEventDispatcher } from 'svelte';
    import { fade, fly } from 'svelte/transition';
    import { openGitHubIssue } from '$lib/githubIssues';

    export let isOpen = false;

    const dispatch = createEventDispatcher();

    let name = '';
    let url = '';
    let description = '';
    
    let submitError = '';

    function close() {
        isOpen = false;
        dispatch('close');
        setTimeout(() => {
            name = '';
            url = '';
            description = '';
            submitError = '';
        }, 300);
    }

    function handleSubmit() {
        if (!name || !url) {
            submitError = 'Name and URL are required.';
            return;
        }

        submitError = '';
        openGitHubIssue({
            title: `New Tool Request: ${name}`,
            body: `### Tool Suggestion\n\n**Name:** ${name}\n**URL:** ${url}\n\n**Description / reason:**\n${description || 'No description provided.'}\n\n---\n*Prepared from the R[AI]DAR tool directory.*`,
            labels: ['enhancement']
        });
        close();
    }

    // Handle Escape key
    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
        if (event.key === 'Escape' && isOpen) {
            close();
        }
    }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
    <!-- Backdrop -->
    <div 
        class="fixed inset-0 bg-[#0c1322]/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        transition:fade={{ duration: 200 }}
    >
        <button type="button" class="absolute inset-0 cursor-default" aria-label="Close tool suggestion dialog" on:click={close}></button>
        <!-- Modal Content -->
        <div 
            class="relative z-10 bg-[#111d33] border border-[#2b3655] rounded-xl shadow-2xl w-full max-w-md overflow-hidden"
            transition:fly={{ y: 20, duration: 300 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="tool-dialog-title"
        >
            <div class="p-5 border-b border-[#2b3655] flex justify-between items-center bg-[#1b2437]/50">
                <h2 id="tool-dialog-title" class="text-xl font-bold text-white">Suggest a Tool</h2>
                <button
                    type="button"
                    aria-label="Close tool suggestion dialog"
                    class="text-[#8e94ae] hover:text-white transition-colors p-1" 
                    on:click={close}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            <div class="p-6">
                    <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                        <p class="text-sm text-[#b2b8cf]">Continue on GitHub to review and submit a public issue. Nothing is sent until you confirm there.</p>
                        <div>
                            <label for="tool-name" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Tool Name *</label>
                            <input 
                                id="tool-name"
                                type="text" 
                                bind:value={name}
                                placeholder="e.g. LangChain" 
                                required
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="tool-url" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Website URL *</label>
                            <input 
                                id="tool-url"
                                type="url" 
                                bind:value={url}
                                placeholder="https://..." 
                                required
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="tool-desc" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Description / Why include it? (Optional)</label>
                            <textarea 
                                id="tool-desc"
                                bind:value={description}
                                placeholder="Briefly describe what it does..." 
                                rows="3"
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all resize-none"
                            ></textarea>
                        </div>

                        {#if submitError}
                            <div class="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-2" in:fade>
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-red-400 shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                                <p class="text-sm text-red-200">{submitError}</p>
                            </div>
                        {/if}

                        <div class="pt-4 flex justify-end gap-3">
                            <button 
                                type="button"
                                on:click={close}
                                class="px-4 py-2.5 text-sm font-medium text-[#b2b8cf] hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button 
                                type="submit"
                                disabled={!name || !url}
                                class="px-5 py-2.5 bg-[#9aa6ff] hover:bg-[#8694ff] disabled:opacity-50 disabled:cursor-not-allowed text-[#0c1322] font-semibold rounded-lg transition-all flex items-center gap-2"
                            >
                                Continue on GitHub
                            </button>
                        </div>
                    </form>
            </div>
        </div>
    </div>
{/if}

<script>
    import { createEventDispatcher } from 'svelte';
    import { fade, fly } from 'svelte/transition';
    import { openGitHubIssue } from '$lib/githubIssues';

    export let isOpen = false;

    const dispatch = createEventDispatcher();

    let type = 'bug'; // 'bug' or 'improvement'
    let title = '';
    let description = '';
    
    let submitError = '';

    function close() {
        isOpen = false;
        dispatch('close');
        setTimeout(() => {
            type = 'bug';
            title = '';
            description = '';
            submitError = '';
        }, 300);
    }

    function handleSubmit() {
        if (!title || !description) {
            submitError = 'Title and description are required.';
            return;
        }

        submitError = '';
        const typeLabel = type === 'bug' ? 'Bug Report' : 'Improvement Suggestion';
        openGitHubIssue({
            title: `[${typeLabel}] ${title}`,
            body: `### ${typeLabel}\n\n**Details:**\n${description}\n\n---\n*Prepared from the R[AI]DAR feedback form.*`,
            labels: [type === 'bug' ? 'bug' : 'enhancement']
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
        class="fixed inset-0 bg-[#0c1322]/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
        transition:fade={{ duration: 200 }}
    >
        <button type="button" class="absolute inset-0 cursor-default" aria-label="Close feedback dialog" on:click={close}></button>
        <!-- Modal Content -->
        <div 
            class="relative z-10 bg-[#111d33] border border-[#2b3655] rounded-xl shadow-2xl w-full max-w-md overflow-hidden"
            transition:fly={{ y: 20, duration: 300 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="feedback-dialog-title"
        >
            <div class="p-5 border-b border-[#2b3655] flex justify-between items-center bg-[#1b2437]/50">
                <h2 id="feedback-dialog-title" class="text-xl font-bold text-white">Feedback</h2>
                <button
                    type="button"
                    aria-label="Close feedback dialog"
                    class="text-[#8e94ae] hover:text-white transition-colors p-1" 
                    on:click={close}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            <div class="p-6">
                    <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                        <p class="text-sm text-[#b2b8cf]">Continue on GitHub to review and submit a public issue. Nothing is sent until you confirm there.</p>
                        <div class="flex gap-4">
                            <label class="flex-1 cursor-pointer">
                                <input type="radio" bind:group={type} value="bug" class="sr-only peer">
                                <div class="px-4 py-3 rounded-lg border border-[#2b3655] bg-[#0c1322] text-[#8e94ae] text-center font-medium transition-all peer-checked:border-red-500/50 peer-checked:bg-red-500/10 peer-checked:text-red-400 hover:bg-[#1b2437]">
                                    Report Bug
                                </div>
                            </label>
                            <label class="flex-1 cursor-pointer">
                                <input type="radio" bind:group={type} value="improvement" class="sr-only peer">
                                <div class="px-4 py-3 rounded-lg border border-[#2b3655] bg-[#0c1322] text-[#8e94ae] text-center font-medium transition-all peer-checked:border-[#9aa6ff] peer-checked:bg-[#9aa6ff]/10 peer-checked:text-[#9aa6ff] hover:bg-[#1b2437]">
                                    Suggest Idea
                                </div>
                            </label>
                        </div>

                        <div>
                            <label for="feedback-title" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Brief Title *</label>
                            <input 
                                id="feedback-title"
                                type="text" 
                                bind:value={title}
                                placeholder="e.g. Search is not working on mobile" 
                                required
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="feedback-desc" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Details *</label>
                            <textarea 
                                id="feedback-desc"
                                bind:value={description}
                                placeholder="Please provide as much detail as possible..." 
                                rows="4"
                                required
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
                                disabled={!title || !description}
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

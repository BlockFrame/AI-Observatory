<script>
    import { createEventDispatcher } from 'svelte';
    import { fade, fly } from 'svelte/transition';

    export let isOpen = false;

    const dispatch = createEventDispatcher();

    let name = '';
    let maker = '';
    let url = '';
    let description = '';
    
    let isSubmitting = false;
    let submitSuccess = false;
    let submitError = '';

    function close() {
        if (!isSubmitting) {
            isOpen = false;
            dispatch('close');
            // Reset state after animation
            setTimeout(() => {
                name = '';
                maker = '';
                url = '';
                description = '';
                submitSuccess = false;
                submitError = '';
            }, 300);
        }
    }

    async function handleSubmit() {
        if (!name || !maker) {
            submitError = 'Model name and maker/provider are required.';
            return;
        }

        isSubmitting = true;
        submitError = '';

        try {
            const response = await fetch('/api/suggest-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, maker, url, description })
            });

            const data = await response.json();

            if (response.ok) {
                submitSuccess = true;
                setTimeout(() => {
                    close();
                }, 2500);
            } else {
                submitError = data.error || 'Something went wrong. Please try again.';
            }
        } catch (error) {
            submitError = 'Network error. Please try again later.';
        } finally {
            isSubmitting = false;
        }
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
        on:click={close}
    >
        <!-- Modal Content -->
        <div 
            class="bg-[#111d33] border border-[#2b3655] rounded-xl shadow-2xl w-full max-w-md overflow-hidden"
            transition:fly={{ y: 20, duration: 300 }}
            on:click|stopPropagation
        >
            <div class="p-5 border-b border-[#2b3655] flex justify-between items-center bg-[#1b2437]/50">
                <h2 class="text-xl font-bold text-white">Suggest a Model</h2>
                <button 
                    class="text-[#8e94ae] hover:text-white transition-colors p-1" 
                    on:click={close}
                    disabled={isSubmitting}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            <div class="p-6">
                {#if submitSuccess}
                    <div class="flex flex-col items-center justify-center py-6 text-center" in:fade>
                        <div class="w-12 h-12 bg-green-500/20 text-green-400 rounded-full flex items-center justify-center mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        </div>
                        <h3 class="text-lg font-medium text-white mb-2">Thank you!</h3>
                        <p class="text-[#b2b8cf]">Your suggestion has been submitted successfully.</p>
                    </div>
                {:else}
                    <form on:submit|preventDefault={handleSubmit} class="space-y-4">
                        <div>
                            <label for="model-name" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Model Name *</label>
                            <input 
                                id="model-name"
                                type="text" 
                                bind:value={name}
                                placeholder="e.g. DeepSeek-V3" 
                                required
                                disabled={isSubmitting}
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="model-maker" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Maker / Provider *</label>
                            <input 
                                id="model-maker"
                                type="text" 
                                bind:value={maker}
                                placeholder="e.g. DeepSeek, OpenAI, Meta" 
                                required
                                disabled={isSubmitting}
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="model-url" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Website / Paper URL (Optional)</label>
                            <input 
                                id="model-url"
                                type="url" 
                                bind:value={url}
                                placeholder="https://..." 
                                disabled={isSubmitting}
                                class="w-full bg-[#0c1322] border border-[#2b3655] rounded-lg px-3 py-2.5 text-white placeholder-[#4a5578] focus:outline-none focus:border-[#9aa6ff] focus:ring-1 focus:ring-[#9aa6ff] transition-all"
                            />
                        </div>

                        <div>
                            <label for="model-desc" class="block text-sm font-medium text-[#cfd5ff] mb-1.5">Specifications / Description (Optional)</label>
                            <textarea 
                                id="model-desc"
                                bind:value={description}
                                placeholder="e.g. 671B MoE model, 128K context window..." 
                                rows="3"
                                disabled={isSubmitting}
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
                                disabled={isSubmitting}
                                class="px-4 py-2.5 text-sm font-medium text-[#b2b8cf] hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button 
                                type="submit"
                                disabled={isSubmitting || !name || !maker}
                                class="px-5 py-2.5 bg-[#9aa6ff] hover:bg-[#8694ff] disabled:opacity-50 disabled:cursor-not-allowed text-[#0c1322] font-semibold rounded-lg transition-all flex items-center gap-2"
                            >
                                {#if isSubmitting}
                                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-[#0c1322]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Submitting...
                                {:else}
                                    Submit Request
                                {/if}
                            </button>
                        </div>
                    </form>
                {/if}
            </div>
        </div>
    </div>
{/if}

import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
    const domain = url.searchParams.get('domain');
    
    if (!domain) {
        return new Response('Missing domain', { status: 400 });
    }

    try {
        // We use Google Favicons as the primary source because it has the largest and most accurate index of real logos.
        // Fetching it server-side completely bypasses client adblockers and tracking protection.
        const iconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
        const response = await fetch(iconUrl);

        if (!response.ok) {
            // Fallback to icon.horse if DuckDuckGo fails
            const fallbackResponse = await fetch(`https://icon.horse/icon/${domain}`);
            if (fallbackResponse.ok) {
                const buffer = await fallbackResponse.arrayBuffer();
                return new Response(buffer, {
                    headers: {
                        'Content-Type': fallbackResponse.headers.get('Content-Type') || 'image/png',
                        'Cache-Control': 'public, max-age=604800'
                    }
                });
            }
            throw new Error('Both primary and fallback icon services failed');
        }

        const buffer = await response.arrayBuffer();
        
        return new Response(buffer, {
            headers: {
                'Content-Type': response.headers.get('Content-Type') || 'image/x-icon',
                'Cache-Control': 'public, max-age=604800' // Cache for 7 days
            }
        });
    } catch (error) {
        console.error(`Failed to fetch icon for ${domain}:`, error);
        
        // Return a generic fallback initial using ui-avatars if all fetching fails on the server
        const fallbackName = domain.charAt(0).toUpperCase();
        const uiAvatarResponse = await fetch(`https://ui-avatars.com/api/?name=${fallbackName}&background=1b2437&color=cfd5ff&size=128`);
        const avatarBuffer = await uiAvatarResponse.arrayBuffer();
        
        return new Response(avatarBuffer, {
            headers: {
                'Content-Type': 'image/png',
                'Cache-Control': 'public, max-age=86400'
            }
        });
    }
};

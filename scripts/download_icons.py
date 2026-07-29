#!/usr/bin/env python3
"""
Download favicons for all tools and models and save them as local static assets.
This is necessary because the app uses adapter-static (no server-side API routes)
and has a strict CSP that blocks external image sources.
"""

import json
import os
import hashlib
import urllib.request
import urllib.error
import time
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ICONS_DIR = os.path.join(PROJECT_DIR, 'frontend', 'static', 'icons')
TOOLS_JSON = os.path.join(PROJECT_DIR, 'frontend', 'static', 'data', 'tools.json')
MODELS_JSON = os.path.join(PROJECT_DIR, 'frontend', 'static', 'data', 'models.json')

# Models domain map (must match the one in models/+page.svelte)
MODEL_DOMAINS = {
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
    'Thinking Machines Lab': 'thinkingmachines.com',
}

# Generate a safe filename from a domain
def domain_to_filename(domain: str) -> str:
    """Convert a domain to a safe filename."""
    safe = domain.replace('.', '_').replace(':', '_').replace('/', '_')
    return safe + '.png'


def download_favicon(domain: str, output_path: str) -> bool:
    """Download a favicon for a domain using Google's favicon service."""
    url = f'https://www.google.com/s2/favicons?domain={domain}&sz=128'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            # Check if we got a valid image (more than 100 bytes — the default globe is ~1.5KB)
            if len(data) > 100:
                with open(output_path, 'wb') as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f'  [WARN] Google failed for {domain}: {e}')

    # Fallback: try icon.horse
    url2 = f'https://icon.horse/icon/{domain}'
    try:
        req2 = urllib.request.Request(url2, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req2, timeout=15) as response:
            data = response.read()
            if len(data) > 100:
                with open(output_path, 'wb') as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f'  [WARN] icon.horse failed for {domain}: {e}')

    return False


def generate_letter_icon(letter: str, output_path: str):
    """Generate a simple SVG letter icon and save as SVG (rename to .png won't matter for <img>)."""
    # We'll save an SVG file with a .svg extension instead
    svg_path = output_path.replace('.png', '.svg')
    colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6']
    color = colors[ord(letter.upper()) % len(colors)]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="24" fill="{color}"/>
  <text x="64" y="64" text-anchor="middle" dominant-baseline="central" 
        font-family="system-ui,-apple-system,sans-serif" font-size="64" font-weight="700" fill="white">
    {letter.upper()}
  </text>
</svg>'''
    with open(svg_path, 'w') as f:
        f.write(svg)
    return svg_path


def download_github_avatar(org: str, output_path: str) -> bool:
    """Download GitHub org/user avatar."""
    url = f'https://github.com/{org}.png?size=128'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            if len(data) > 500:  # GitHub avatars are typically large
                with open(output_path, 'wb') as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f'  [WARN] GitHub avatar failed for {org}: {e}')
    return False


def get_icon_key(url: str) -> str:
    """Get the icon key for a tool URL.
    
    For GitHub URLs: returns 'github_com__{org}' (double underscore separator)
    For other URLs: returns the domain with dots replaced by underscores
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        if hostname == 'github.com':
            parts = parsed.path.strip('/').split('/')
            org = parts[0] if parts else ''
            if org:
                return f'github_com__{org}'
        return hostname.replace('.', '_').replace(':', '_').replace('/', '_')
    except:
        return 'example_com'


def main():
    os.makedirs(ICONS_DIR, exist_ok=True)

    # Collect regular domains and GitHub orgs separately
    regular_domains = set()
    github_orgs = set()

    # From tools
    if os.path.exists(TOOLS_JSON):
        with open(TOOLS_JSON) as f:
            tools = json.load(f)
        for tool in tools:
            try:
                parsed = urlparse(tool['url'])
                hostname = parsed.hostname
                if not hostname:
                    continue
                if hostname == 'github.com':
                    parts = parsed.path.strip('/').split('/')
                    org = parts[0] if parts else None
                    if org:
                        github_orgs.add(org)
                else:
                    regular_domains.add(hostname)
            except:
                pass
        print(f'Tools: {len(tools)} entries')
        print(f'  Regular domains: {len(regular_domains)}')
        print(f'  GitHub orgs: {len(github_orgs)}')

    # From models domain map
    for maker, domain in MODEL_DOMAINS.items():
        regular_domains.add(domain)
    
    total = len(regular_domains) + len(github_orgs)
    print(f'Total to fetch: {total} ({len(regular_domains)} domains + {len(github_orgs)} GitHub orgs)')

    success = 0
    failed = 0
    skipped = 0
    idx = 0

    # Download regular domain favicons
    for domain in sorted(regular_domains):
        idx += 1
        filename = domain_to_filename(domain)
        output_path = os.path.join(ICONS_DIR, filename)
        svg_fallback = output_path.replace('.png', '.svg')
        
        if os.path.exists(output_path) or os.path.exists(svg_fallback):
            skipped += 1
            continue
        
        print(f'[{idx}/{total}] Downloading {domain}...')
        
        if download_favicon(domain, output_path):
            success += 1
        else:
            letter = domain[0]
            generated = generate_letter_icon(letter, output_path)
            print(f'  -> Generated letter icon: {os.path.basename(generated)}')
            failed += 1
        
        if idx % 20 == 0:
            time.sleep(1)

    # Download GitHub org avatars
    for org in sorted(github_orgs):
        idx += 1
        filename = f'github_com__{org}.png'
        output_path = os.path.join(ICONS_DIR, filename)
        svg_fallback = output_path.replace('.png', '.svg')
        
        if os.path.exists(output_path) or os.path.exists(svg_fallback):
            skipped += 1
            continue
        
        print(f'[{idx}/{total}] Downloading GitHub avatar: {org}...')
        
        if download_github_avatar(org, output_path):
            success += 1
        else:
            letter = org[0]
            generated = generate_letter_icon(letter, output_path)
            print(f'  -> Generated letter icon: {os.path.basename(generated)}')
            failed += 1
        
        if idx % 20 == 0:
            time.sleep(1)

    print(f'\nDone! Success: {success}, Letter fallback: {failed}, Skipped (cached): {skipped}')
    print(f'Icons saved to: {ICONS_DIR}')


if __name__ == '__main__':
    main()


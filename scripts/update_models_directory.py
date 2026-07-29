#!/usr/bin/env python3
"""
Update Models Directory Script
Scrapes the latest models from ai-tldr.dev/models/ and categorizes them
into the 15 exact Makers and their respective families.
Saves the output to frontend/static/data/models.json.

Dependencies:
pip install playwright bs4
playwright install chromium
"""

import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '../frontend/static/data/models.json')

MAKERS = [
    "Anthropic", "OpenAI", "Google", "Meta", "DeepSeek", "Alibaba (Qwen)", 
    "Moonshot AI (Kimi)", "Z.ai (Zhipu / GLM)", "xAI (Grok)", "Mistral AI", 
    "Cohere", "MiniMax", "ByteDance", "Tencent", "Thinking Machines Lab"
]

FAMILIES = {
    "Anthropic": ["Claude Fable / Mythos (Mythos-class)", "Claude Opus", "Claude Sonnet", "Claude Haiku", "Claude (legacy 1–2.x)"],
    "OpenAI": ["GPT-5", "GPT-4o", "GPT-4", "o1 / o3", "GPT-3.5"],
    "Google": ["Gemini 2.0", "Gemini 1.5", "Gemma 3", "Gemma 2", "Gemma 1", "PaLM"],
    "Meta": ["Llama 3.2", "Llama 3.1", "Llama 3", "Llama 2"],
    "Mistral AI": ["Mistral Large", "Mistral NeMo", "Codestral", "Mixtral", "Mistral 7B"],
    "DeepSeek": ["DeepSeek-V3", "DeepSeek-R1", "DeepSeek-Coder-V2"],
    "xAI (Grok)": ["Grok-3", "Grok-2", "Grok-1"],
    "Alibaba (Qwen)": ["Qwen 2.5", "Qwen 2", "Qwen 1.5"],
    "Z.ai (Zhipu / GLM)": ["GLM-4", "GLM-3"],
    "Moonshot AI (Kimi)": ["Moonshot-v1"],
    "Cohere": ["Command R+", "Command R"],
    "MiniMax": ["abab6", "abab5"],
    "ByteDance": ["Doubao"],
    "Tencent": ["Hunyuan"],
    "Thinking Machines Lab": ["TML-1"]
}

def extract_models():
    print("Launching headless browser to scrape ai-tldr.dev/models/...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://ai-tldr.dev/models/', wait_until='networkidle')
        page.wait_for_timeout(3000) # Ensure JS is hydrated
        
        html = page.content()
        browser.close()
        
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    
    models = []
    # Find the JSON-LD script containing the models
    for script in scripts:
        if script.string and len(script.string) > 10000:
            try:
                data = json.loads(script.string)
                if "mainEntity" in data and "itemListElement" in data["mainEntity"]:
                    items = data["mainEntity"]["itemListElement"]
                    for item in items:
                        models.append({
                            "name": item.get("name"),
                            "description": item.get("description"),
                            "url": item.get("url")
                        })
                    break
            except Exception:
                continue
                
    if not models:
        print("Error: Could not find model data in the DOM.")
        return []
        
    print(f"Extracted {len(models)} raw models.")
    return models

def categorize_models(models):
    processed_models = []
    
    for m in models:
        name = m.get('name', '')
        desc = m.get('description', '')
        text = (name + ' ' + desc).lower()
        
        maker = "Other"
        
        # 1. Map Maker exactly as listed
        if 'anthropic' in text or 'claude' in name.lower(): maker = 'Anthropic'
        elif 'openai' in text or 'gpt-' in name.lower() or 'o1-' in name.lower() or 'o3-' in name.lower(): maker = 'OpenAI'
        elif 'google' in text or 'gemini' in name.lower() or 'gemma' in name.lower() or 'palm' in text: maker = 'Google'
        elif 'meta' in text or 'llama' in name.lower(): maker = 'Meta'
        elif 'deepseek' in name.lower(): maker = 'DeepSeek'
        elif 'qwen' in name.lower() or 'alibaba' in text: maker = 'Alibaba (Qwen)'
        elif 'moonshot' in text or 'kimi' in name.lower(): maker = 'Moonshot AI (Kimi)'
        elif 'zhipu' in text or 'glm-' in name.lower() or 'z.ai' in text: maker = 'Z.ai (Zhipu / GLM)'
        elif 'xai' in text or 'grok' in name.lower(): maker = 'xAI (Grok)'
        elif 'mistral' in text or 'mixtral' in name.lower() or 'codestral' in name.lower() or 'mathstral' in name.lower(): maker = 'Mistral AI'
        elif 'cohere' in text or 'command' in name.lower() or 'aya' in name.lower(): maker = 'Cohere'
        elif 'minimax' in text or 'abab' in name.lower(): maker = 'MiniMax'
        elif 'bytedance' in text or 'doubao' in name.lower(): maker = 'ByteDance'
        elif 'tencent' in text or 'hunyuan' in name.lower(): maker = 'Tencent'
        elif 'thinking machines' in text or 'tml-' in name.lower(): maker = 'Thinking Machines Lab'
        
        # Keep only the exact 15 makers
        if maker not in MAKERS:
            # Attempt a fallback for hidden ones or drop them
            if 'databricks' in text or 'dbrx' in name.lower(): maker = 'Cohere'
            else: continue
            
        m['category'] = maker
        
        # 2. Map Family based on Maker's exact subcategories
        n = name.lower()
        family = "Other"
        
        if maker == 'Anthropic':
            if 'fable' in n or 'mythos' in n: family = 'Claude Fable / Mythos (Mythos-class)'
            elif 'opus' in n: family = 'Claude Opus'
            elif 'sonnet' in n: family = 'Claude Sonnet'
            elif 'haiku' in n: family = 'Claude Haiku'
            else: family = 'Claude (legacy 1–2.x)'
        elif maker == 'OpenAI':
            if 'gpt-5' in n: family = 'GPT-5'
            elif 'gpt-4o' in n: family = 'GPT-4o'
            elif 'gpt-4' in n: family = 'GPT-4'
            elif 'o1' in n or 'o3' in n: family = 'o1 / o3'
            else: family = 'GPT-3.5'
        elif maker == 'Google':
            if 'gemini 2' in n: family = 'Gemini 2.0'
            elif 'gemini 1' in n: family = 'Gemini 1.5'
            elif 'gemma 3' in n: family = 'Gemma 3'
            elif 'gemma 2' in n: family = 'Gemma 2'
            elif 'gemma' in n: family = 'Gemma 1'
            else: family = 'PaLM'
        elif maker == 'Meta':
            if 'llama 3.2' in n: family = 'Llama 3.2'
            elif 'llama 3.1' in n: family = 'Llama 3.1'
            elif 'llama 3' in n: family = 'Llama 3'
            else: family = 'Llama 2'
        elif maker == 'DeepSeek':
            if 'v3' in n: family = 'DeepSeek-V3'
            elif 'r1' in n: family = 'DeepSeek-R1'
            elif 'coder' in n: family = 'DeepSeek-Coder-V2'
            else: family = 'DeepSeek-V3'
        elif maker == 'Mistral AI':
            if 'large' in n: family = 'Mistral Large'
            elif 'nemo' in n: family = 'Mistral NeMo'
            elif 'codestral' in n: family = 'Codestral'
            elif 'mixtral' in n: family = 'Mixtral'
            else: family = 'Mistral 7B'
        elif maker == 'xAI (Grok)':
            if 'grok-3' in n: family = 'Grok-3'
            elif 'grok-2' in n: family = 'Grok-2'
            else: family = 'Grok-1'
        elif maker == 'Alibaba (Qwen)':
            if '2.5' in n: family = 'Qwen 2.5'
            elif '2' in n: family = 'Qwen 2'
            else: family = 'Qwen 1.5'
        elif maker == 'Cohere':
            if 'r+' in n: family = 'Command R+'
            else: family = 'Command R'
        else:
            if maker in FAMILIES:
                family = FAMILIES[maker][0]
            else:
                family = maker
                
        m['subcategory'] = family
        processed_models.append(m)
        
    return processed_models

def main():
    raw_models = extract_models()
    if not raw_models:
        return
        
    final_models = categorize_models(raw_models)
    
    print(f"Mapped {len(final_models)} models perfectly to the {len(MAKERS)} exact makers.")
    
    # Save to frontend data directory
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_models, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

import json

def get_subcategory(provider, name):
    name_lower = name.lower()
    
    if provider == "Alibaba (Qwen)":
        if "qwen3" in name_lower or "qwen 3" in name_lower: return "Qwen 3"
        if "qwen2.5" in name_lower or "qwen 2.5" in name_lower: return "Qwen 2.5"
        if "qwen2" in name_lower or "qwen 2" in name_lower: return "Qwen 2"
        if "qwen1.5" in name_lower or "qwen 1.5" in name_lower: return "Qwen 1.5"
        return "Qwen (Other)"
        
    if provider == "Anthropic":
        if "opus" in name_lower: return "Claude Opus"
        if "sonnet" in name_lower: return "Claude Sonnet"
        if "haiku" in name_lower: return "Claude Haiku"
        if "mythos" in name_lower or "fable" in name_lower: return "Claude Fable / Mythos"
        return "Claude (legacy 1-2.x)"
        
    if provider == "Cohere":
        if "command a" in name_lower or "aya" in name_lower: return "Command A / Aya"
        if "command r+" in name_lower: return "Command R+"
        if "command r" in name_lower: return "Command R"
        return "Command (Legacy)"
        
    if provider == "DeepSeek":
        if "r1" in name_lower: return "DeepSeek-R1"
        if "v4" in name_lower: return "DeepSeek-V4"
        if "v3" in name_lower: return "DeepSeek-V3"
        if "v2" in name_lower: return "DeepSeek-V2"
        if "coder" in name_lower: return "DeepSeek Coder"
        return "DeepSeek V1 / Legacy"
        
    if provider == "Google":
        if "med-palm" in name_lower: return "PaLM"
        if "med-gemini" in name_lower: return "Med-Gemini"
        if "gemma 4" in name_lower or "diffusiongemma" in name_lower: return "Gemma 4"
        if "gemma 3" in name_lower: return "Gemma 3"
        if "gemma 2" in name_lower: return "Gemma 2"
        if "gemma 1" in name_lower or name == "Gemma": return "Gemma 1"
        if "gemini 3" in name_lower or "gemini-3" in name_lower or "gemini diffusion" in name_lower: return "Gemini 3"
        if "gemini 2" in name_lower or "gemini-2" in name_lower: return "Gemini 2"
        if "gemini 1" in name_lower or "gemini-1" in name_lower: return "Gemini 1"
        return "Gemini (Other)"
        
    if provider == "Meta":
        if "muse" in name_lower: return "Muse / Experimental"
        if "code llama" in name_lower: return "Code Llama"
        if "llama 4" in name_lower: return "Llama 4"
        if "llama 3.3" in name_lower: return "Llama 3.3"
        if "llama 3.2" in name_lower: return "Llama 3.2"
        if "llama 3.1" in name_lower: return "Llama 3.1"
        if "llama 3" in name_lower: return "Llama 3"
        if "llama 2" in name_lower: return "Llama 2"
        return "LLaMA 1"
        
    if provider == "MiniMax":
        if "abab6" in name_lower: return "abab6"
        if "abab5" in name_lower: return "abab5"
        if "m3" in name_lower: return "MiniMax M3"
        if "m2" in name_lower: return "MiniMax M2"
        if "m1" in name_lower: return "MiniMax M1"
        return "MiniMax (Other)"
        
    if provider == "Mistral AI":
        if "codestral" in name_lower or "mathstral" in name_lower: return "Codestral / Mathstral"
        if "pixtral" in name_lower: return "Pixtral"
        if "mixtral" in name_lower: return "Mixtral"
        if "large" in name_lower: return "Mistral Large"
        if "medium" in name_lower or "magistral" in name_lower: return "Mistral Medium"
        if "small" in name_lower: return "Mistral Small"
        return "Mistral Base"
        
    if provider == "Moonshot AI (Kimi)":
        if "k3" in name_lower: return "Kimi K3"
        if "k2" in name_lower: return "Kimi K2"
        if "k1" in name_lower or "moonshot" in name_lower: return "Moonshot v1"
        return "Kimi (Other)"
        
    if provider == "OpenAI":
        if "gpt-oss" in name_lower: return "GPT-OSS"
        if "rosalind" in name_lower: return "Experimental / Special"
        if "gpt-5" in name_lower: return "GPT-5"
        if "gpt-4o" in name_lower: return "GPT-4o"
        if "gpt-4" in name_lower: return "GPT-4"
        if "gpt-3" in name_lower: return "GPT-3.5"
        return "OpenAI (Other)"
        
    if provider == "Z.ai (Zhipu / GLM)":
        if "auto" in name_lower: return "AutoGLM"
        if "glm-5" in name_lower: return "GLM-5"
        if "glm-4" in name_lower: return "GLM-4"
        return "GLM (Other)"
        
    if provider == "xAI (Grok)":
        if "grok 4" in name_lower: return "Grok 4"
        if "grok 3" in name_lower: return "Grok 3"
        if "grok 2" in name_lower: return "Grok 2"
        if "grok 1" in name_lower or "grok code" in name_lower: return "Grok 1"
        if "grok build" in name_lower: return "Grok Build"
        return "Grok (Other)"
        
    if provider == "Tencent":
        return "Hunyuan"

    return "Other"

with open("frontend/static/data/models.json") as f:
    data = json.load(f)

for m in data:
    provider = m.get("category", "Unknown")
    name = m.get("name", "")
    new_sub = get_subcategory(provider, name)
    m["subcategory"] = new_sub
    
    # Also fix any weird providers if any Meta models were assigned to DeepSeek or something
    if "DeepSeek-R1-Distill-Llama" in name:
        m["category"] = "DeepSeek"
        m["subcategory"] = "DeepSeek-R1 (Distill)"
    elif "DeepSeek-R1-Distill-Qwen" in name:
        m["category"] = "DeepSeek"
        m["subcategory"] = "DeepSeek-R1 (Distill)"

with open("frontend/static/data/models.json", "w") as f:
    json.dump(data, f, indent=2)
    
with open("web/data/models.json", "w") as f:
    json.dump(data, f, indent=2)

print("Done fixing models")

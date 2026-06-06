import google.generativeai as genai

# Paste your REAL API key right here for the test
genai.configure(api_key="YOUR_REAL_API_KEY_HERE")

print("Available Models for this API Key:")
print("-" * 30)

# Ask Google to list every model this key is allowed to use
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
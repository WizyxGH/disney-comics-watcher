import json
import base64
import requests
import re

CHARACTER_CODE_MAP = {
    "picsou": "US",
    "oncle picsou": "US",
    "donald": "DD",
    "donald duck": "DD",
    "mickey": "MM",
    "mickey mouse": "MM",
    "dingo": "GO",
    "pluto": "PL",
    "riri": "HDL",
    "fifi": "HDL",
    "loulou": "HDL",
    "riri/fifi/loulou": "HDL",
    "riri, fifi et loulou": "HDL",
    "riri, fifi, loulou": "HDL",
    "géo trouvetou": "GY",
    "geo trouvetou": "GY",
    "gontran": "GL",
    "gontran bonheur": "GL",
    "daisy": "DA",
    "daisy duck": "DA",
    "minnie": "MI",
    "minnie mouse": "MI",
    "rapetou": "BB",
    "les rapetou": "BB",
    "miss tick": "MD",
    "misstick": "MD",
    "gripsou": "FG",
    "archibald gripsou": "FLG",
    "flairsou": "RKD",
    "fantomiald": "PK",
    "popop": "FE",
    "gaston": "FE",
    "fantôme noir": "PB",
    "fantome noir": "PB",
    "le fantôme noir": "PB",
    "le fantome noir": "PB",
    "gus": "GG",
    "grand-mère donald": "GD",
    "grand-mere donald": "GD",
    "clarabelle": "CC",
    "horace": "HH",
    "jojo et michou": "MF",
    "commissaire finot": "CO",
    "inspecteur duflair": "DC",
    "gamma": "EB",
    "fergus mcpicsou": "FMc",
    "downy mcpicsou": "DOD",
    "hortense mcpicsou": "HM",
    "matilda mcpicsou": "MMc",
    "goldie": "Go",
    "pat hibulaire": "PE",
}

VALID_CHARACTER_CODES = set(CHARACTER_CODE_MAP.values())

# Generate a concise unique list for the prompt (e.g. "- Picsou (US)")
prompt_chars = []
_seen_codes = set()
for name, code in CHARACTER_CODE_MAP.items():
    if code not in _seen_codes:
        prompt_chars.append(f"- {name.title()} ({code})")
        _seen_codes.add(code)
PROMPT_CHAR_LIST = "\n".join(prompt_chars)

def analyze_cover_with_gemini(cover_url: str, api_key: str) -> dict:
    """Uses the Gemini API to extract the main cover story/title
    and detect the Disney characters present on the cover image in a single call.
    
    Returns a dictionary:
      {
        "title": str | None,
        "characters": list[dict]  # list of {"name_fr": str, "code": str | None}
      }
    """
    fallback_res = {"title": None, "characters": []}
    if not cover_url or not api_key:
        return fallback_res
    try:
        # Download the image
        resp = requests.get(cover_url, timeout=15)
        resp.raise_for_status()
        img_bytes = resp.content
        
        # Determine MIME type
        mime_type = resp.headers.get("Content-Type", "image/jpeg")
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"
            
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        
        # Call Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an assistant specialized in Disney comics and the Inducks database.\n"
                                "Analyze the cover image of a French Disney magazine or comic book.\n"
                                "Perform two tasks:\n"
                                "1. Identify and extract the main headline, featured story title, or major theme of this specific issue "
                                "(usually written in large, prominent, stylized letters at the bottom or middle of the cover, "
                                "like 'Escape game dans le coffre de Picsou' or 'Destination aventure !'). "
                                "Do NOT extract secondary sidebar text, barcode numbers, prices, or the main magazine name (e.g. 'Picsou Magazine', 'Le Journal de Mickey'). "
                                "Return it under the 'title' key (sentence casing, without quotes, in French). If no major feature title is visible, set it to null.\n\n"
                                "2. Identify all main Disney characters visible on the cover. For each, return their French name "
                                "and their official standard Inducks character code if known. Use the following exact mappings for reference:\n"
                                f"{PROMPT_CHAR_LIST}\n\n"
                                "If a character is not in this list, return their French name and set 'code' to null. "
                                "Do NOT invent character codes. Return this list under the 'characters' key, where each item is an object with 'name_fr' and 'code'.\n\n"
                                "Format the output as a JSON object with keys 'title' and 'characters'. Example:\n"
                                '{\n  "title": "Escape game chez Picsou",\n  "characters": [\n    {"name_fr": "Picsou", "code": "US"},\n    {"name_fr": "Donald Duck", "code": "DD"}\n  ]\n}'
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": img_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "maxOutputTokens": 300
            }
        }
        
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        result = r.json()
        
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        data = json.loads(text)
        
        title = data.get("title")
        if title:
            title = re.sub(r'^["\'\-\*#`\s]+', '', title)
            title = re.sub(r'["\'\-\*#`\s]+$', '', title)
            if not title.strip():
                title = None
            else:
                title = title.strip()
        
        characters = data.get("characters", [])
        cleaned_chars = []
        if isinstance(characters, list):
            for char in characters:
                if isinstance(char, dict) and "name_fr" in char:
                    name_fr = char["name_fr"].strip()
                    norm_name = name_fr.lower()
                    
                    # 1. First search in our mapping
                    code = CHARACTER_CODE_MAP.get(norm_name)
                    if not code:
                        for k, v in CHARACTER_CODE_MAP.items():
                            if k == norm_name or norm_name.startswith(k) or k.startswith(norm_name):
                                code = v
                                break
                                
                    # 2. Strict whitelist fallback: only allow the code if it's explicitly in the map's values
                    if not code and char.get("code"):
                        provided_code = char["code"].strip()
                        if provided_code in VALID_CHARACTER_CODES:
                            code = provided_code
                    
                    cleaned_chars.append({
                        "name_fr": name_fr,
                        "code": code
                    })
                    
        return {"title": title, "characters": cleaned_chars}
        
    except Exception as e:
        print(f"  [warn] Failed to analyze cover with Gemini: {e}")
        return fallback_res

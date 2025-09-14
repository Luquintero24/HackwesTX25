import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model_ai = genai.GenerativeModel("gemini-1.5-flash")

# Prepare structured data for Gemini
summary_input = {
    "top_risks": top_risks.to_dict(orient="records"),
    "similarities": {
        "ENG-12 vs Overheating": float(model.wv.similarity("ENG-12", "Overheating")),
        "ENG-12 vs High vibration": float(model.wv.similarity("ENG-12", "High vibration")),
    },
    "pads": df.groupby("pad_id")["severity"].apply(list).to_dict(),
}

# Send to Gemini
prompt = f"""
You are an oilfield risk detection assistant. 
Given this knowledge graph analysis, generate a daily summary for managers.

Data:
{summary_input}

Please provide:
1. A PAD summary (by pad_id with severity issues).
2. A component risk summary (focus on subj_type='component').
3. Managerial takeaways (which components to check immediately, which to monitor).
"""

response = model_ai.generate_content(prompt)
print("\n📊 Gemini AI-Generated Summary")
print(response.text)

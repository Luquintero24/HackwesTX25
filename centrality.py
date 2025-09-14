import os
import pandas as pd
import networkx as nx
from sqlalchemy import create_engine
from node2vec import Node2Vec
from dotenv import load_dotenv
import google.generativeai as genai
import re
from joblib import Parallel, delayed

# ================================
# 1. Load environment & DB connect
# ================================
load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# ================================
# 2. Load data from kg_facts
# ================================
query = """
SELECT subj_text, subj_type, predicate, obj_text, obj_type, severity, pad_id
FROM kg_facts
"""
df = pd.read_sql(query, engine)

# Normalize severity
df["severity"] = df["severity"].fillna("NORMAL")

# ================================
# 3. Build directed graph
# ================================
G = nx.DiGraph()
for _, row in df.iterrows():
    G.add_node(row["subj_text"], type=row["subj_type"], severity=row["severity"])
    G.add_node(row["obj_text"], type=row["obj_type"], severity=row["severity"])
    G.add_edge(row["subj_text"], row["obj_text"], predicate=row["predicate"])

# ================================
# 4. Compute centrality
# ================================
degree_centrality = nx.degree_centrality(G)
betweenness_centrality = nx.betweenness_centrality(G)
closeness_centrality = nx.closeness_centrality(G)

# ================================
# 5. Centrality DataFrame
# ================================
severity_rank = {"HIGH": 3, "MED": 2, "NORMAL": 1}
centrality_df = pd.DataFrame({
    "node": list(G.nodes()),
    "degree": [degree_centrality.get(n, 0) for n in G.nodes()],
    "betweenness": [betweenness_centrality.get(n, 0) for n in G.nodes()],
    "closeness": [closeness_centrality.get(n, 0) for n in G.nodes()],
    "severity": [G.nodes[n].get("severity", "NORMAL") for n in G.nodes()],
    "type": [G.nodes[n].get("type", "") for n in G.nodes()],
})
centrality_df["severity_rank"] = centrality_df["severity"].map(severity_rank)
centrality_df = centrality_df.sort_values(
    ["severity_rank", "degree"], ascending=[False, False]
)

# ================================
# 6. Top Risks
# ================================
top_risks = centrality_df.head(10)
print("🚨 Top Risky Nodes in Knowledge Graph 🚨")
for _, row in top_risks.iterrows():
    print(
        f"- {row['node']} ({row['type']}, severity={row['severity']}): "
        f"degree={row['degree']:.2f}, betweenness={row['betweenness']:.2f}, closeness={row['closeness']:.2f}"
    )

# ================================
# 7. Node2Vec embeddings & similarity
# ================================
node2vec = Node2Vec(G.to_undirected(), dimensions=32, walk_length=10, num_walks=100, workers=4)
model = node2vec.fit(window=5, min_count=1, batch_words=4)

nodes = list(G.nodes())

def compute_similarity(i, j):
    try:
        sim = model.wv.similarity(nodes[i], nodes[j])
        return {"node1": nodes[i], "node2": nodes[j], "similarity": float(sim)}
    except KeyError:
        return None

# Run in parallel with 8 processes (you can tune this)
similarities = Parallel(n_jobs=8, backend="loky")(
    delayed(compute_similarity)(i, j)
    for i in range(len(nodes))
    for j in range(i + 1, len(nodes))
)

# Remove Nones
similarities = [s for s in similarities if s is not None]

# Sort similarities
similarities = sorted(similarities, key=lambda x: x["similarity"], reverse=True)
top_similarities = similarities[:10]

print("\n🔮 Top Node Similarities")
for sim in top_similarities:
    print(f"{sim['node1']} ↔ {sim['node2']} = {sim['similarity']:.3f}")

# ================================
# 8. Aggregate risks by PAD
# ================================
pad_risks = (
    df[df["severity"].isin(["HIGH", "MED"])]
    .groupby("pad_id")[["subj_text", "obj_text", "severity"]]
    .apply(lambda g: g.to_dict(orient="records"))
    .to_dict()
)

# ================================
# 9. AI Summary with Gemini
# ================================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model_ai = genai.GenerativeModel("gemini-1.5-flash")

summary_input = {
    "top_risks": top_risks.to_dict(orient="records"),
    "similarities": top_similarities,
    "pads": pad_risks,
}

prompt = f"""
You are an oilfield risk detection assistant. 
Given this knowledge graph analysis, generate a daily summary for managers. Summarize today's knowledge graph analysis in few bullet-point daily risk report.

Data:
{summary_input}

⚠️ RULES:
- ONLY use the exact components, pads, and symptoms listed in the data below.
- Be concise and manager-friendly.

Format:
1. PAD Summary → For each PAD, give a summary of the day for that pad describing the specific components that are at higher risk
2. Component Risks → List ONLY real components with severity and why needs to be checkedd
3. Actions → Inspect Now: Components that must be inspected immediately (HIGH) and Monitor: Components that should be watched (MED risk).
"""

response = model_ai.generate_content(prompt)

print("\n Report Summary")

# Clean markdown-style bold (**text**)
clean_summary = re.sub(r"\*\*(.*?)\*\*", r"\1", response.text)

# Save to file
output_file = "daily_risk_summary.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(clean_summary)

print(f"\n✅ Clean summary saved to {output_file}")
# Inspiration
Oilfield operations generate hundreds of unstructured emails daily with critical data about equipment status. Detecting risks manually is slow and prone to errors. We wanted to automate this process and turn unstructured text into actionable insights.

# What it does
Our project performs automated risk detection by extracting metrics from unstructured emails, converting them into a knowledge graph (KG), and running parallel graph analytics to detect high-risk components and generate daily summaries for managers.

# How we built it
Gemini API: Extracted structured metrics and severity levels from emails.

PostgreSQL: Stored facts and linked them with pads, components, and metrics.

Knowledge Graph: Built using C++, with severity-aware nodes and relationships.

Graph Analytics: Applied centrality and Node2Vec embeddings, accelerated with parallelism.

AI Summaries: Gemini generated concise risk reports (Inspect Now / Monitor).

FrontEnd: TypeScript, React, Vite, Tailwind CSS

# Challenges we ran into
Extracting accurate keywords and relationships to populate the KG.

Efficiently fetching and processing data from the database.

Gemini API hallucination

# Accomplishments that we're proud of
Successfully created a knowledge graph from noisy emails.

Implemented graph analytics with good predictive power.

Leveraged parallelism to scale analytics efficiently.

# What we learned
How to design and analyze knowledge graphs for real-world risk detection.

Integrating Postgres, TypeScript services, and Gemini API.

Using graph embeddings and centrality to uncover risks.

What's next for Nodary
We plan to scale with real company data and customize the pipeline for different industries. Tailoring risk detection to specific business needs will maximize impact and adoption.

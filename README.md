# GitHub Tuner

**GitHub Tuner** is an autonomous, hybrid-AI research assistant that finds, filters, and curates GitHub repositories based on your interests. It transforms repository discovery from a manual search into an intelligent, self-optimizing pipeline.

## 🚀 Features

*   **Hybrid AI Architecture**:
    *   **The Hunter**: Scrapes GitHub API for raw candidates based on dynamic strategies.
    *   **The Screener (Local AI)**: Uses local vector embeddings (`sentence-transformers`) to filter noise and find relevant matches without API costs.
    *   **The Analyst (Cloud AI)**: Uses LLMs (Gemini 1.5 Flash) to analyze high-potential repos and generate summaries.
    *   **The Manager**: Learns from your feedback to optimize search strategies over time.
*   **Feedback Loop**: Vote on findings to train the agent on what you like.
*   **Efficient**: Only sends high-quality candidates to the cloud LLM.

## 📦 Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/github-tuner.git
    cd github-tuner
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Set up environment variables:
    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    export GITHUB_TOKEN="your_github_token_here" # Optional, for higher rate limits
    ```

## 🛠 Usage

### 1. Start Tuning
Run the discovery pipeline. The agent will hunt, screen, and analyze repositories.
```bash
python3 -m tuner.cli start
```

### 2. View Findings
List the pending repositories found by the agent.
```bash
python3 -m tuner.cli list
```

### 3. Provide Feedback
Vote on findings to help the agent learn.
```bash
python3 -m tuner.cli vote <ID> up   # Like
python3 -m tuner.cli vote <ID> down # Dislike
```

### 4. Optimize Strategy
Tell the agent to analyze your feedback and update its search strategy.
```bash
python3 -m tuner.cli optimize
```

## ⚙️ Configuration

The search strategy is stored in `strategy.json`. You can manually edit it or let the agent optimize it.

```json
{
    "keywords": ["machine learning", "autonomous agents"],
    "languages": ["Python", "Rust"],
    "min_stars": 50
}
```

## 🏗 Architecture

*   **src/tuner/hunter.py**: Data ingestion from GitHub.
*   **src/tuner/brain.py**: AI logic (Local embeddings + Cloud LLM).
*   **src/tuner/storage.py**: SQLite database management.
*   **src/tuner/cli.py**: Command-line interface and orchestration.

## 📄 License

MIT License

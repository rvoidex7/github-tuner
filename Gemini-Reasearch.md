#  **GitHub Tuner: Autonomous Code Discovery and Context-Aware Asynchronous Architecture Evolution Report**

## **1\. Executive Summary and Current State of the System**

The logarithmic growth of the software development ecosystem has created a paradoxical problem for developers: the inability to access qualified tools amidst an abundance of code. The current 'github-tuner' project aims to solve this problem with an "intelligent hunter" approach, operating as a hybrid AI system. Based on data from antigravityChat.txt and other analysis files, the system currently operates at the level of a "Lucky Intern". The existing architecture scans the superficial layers of the GitHub API (first 50-100 results), performs local filtering based on titles and short descriptions (LocalBrain), and only activates Large Language Models (LLM) like Gemini for "elite" candidates in the final stage. While cost-efficient, this structure suffers from an epistemological "Blind Spot" problem; GitHub's strict 1,000-result API limit and linear scanning logic prevent the system from discovering deep "hidden gems".  
This report presents a comprehensive architectural transformation plan required to evolve the 'github-tuner' project from a reactive script into a proactive, context-aware, and resilient "Senior Research Agent." The three core capabilities requested by the user—context-specific research, continuous operation via asynchronous task queues, and deep data mining via date slicing—have been detailed by combining modern distributed system principles with machine learning strategies.  
The proposed architecture aims to achieve a "Chill Mode" structure: running 24/7 in the background without user intervention, respecting API limits but free from inefficient pauses. This transformation requires migrating synchronous (blocking) Python code to asynchronous (non-blocking) Event Loops, replacing static strategy files with probabilistic Reinforcement Learning algorithms, and making the database layer suitable for high concurrency.

## **2\. Analysis of Current Architecture and Critical Bottlenecks**

Before proceeding with the development plan, a technical autopsy must be performed to understand why the current system "fetches the same results" and "stalls."

### **2.1 Static Window and Recurrence Problem**

The current discover.py (or the new hunter.py) module sends requests to the GitHub API with parameters like sort:updated or sort:stars. The GitHub Search API is deterministic by nature. The same query (e.g., "machine learning language:python"), when made in the same timeframe, always returns the same 1,000 repositories in the same order. When the user scans up to the 5th page, the system sees these "most popular" 50 repositories repeatedly every time it runs. Even if it doesn't re-save them due to db checks, it wastes API quota fetching this known data and never reaches the 1,001st repository. This is the fundamental technical reason for the user complaint of "constantly seeing the same results."

### **2.2 Synchronous Blocking and Inefficiency**

The current structure follows a linear loop of "Search \-\> Download \-\> Analyze \-\> Save." When Python's standard requests or httpx (in synchronous mode) libraries are used, the CPU waits idly until a response is received (I/O Blocking). More importantly, when hitting the GitHub API Rate Limit, the code puts the entire system to sleep with time.sleep(). During this time, data that has been downloaded but not yet analyzed waits in memory. Completely stopping the system instead of "processing the data at hand" is a major waste of resources.

### **2.3 Context-Blindness**

Currently, LocalBrain extracts an average vector of all the user's stars (starred\_repos) or searches based on keywords in strategy.json. However, when the user says, "Today, research only embedded system libraries written in Rust," the system's general "average profile" might perceive this specific request as noise and suppress it. The current architecture lacks a mechanism to define an immediate and specific "Target Vector."

## **Section 3: Context-Aware Research Architecture**

The user's demand to "research specific to a repo or category, not just all my stars" requires the system to switch from "General Discovery" mode to "Targeted Intelligence" mode. To achieve this, I propose the "Dynamic Context Injection" architecture.

### **3.1 Targeting in Vector Space**

In the current system, LocalBrain uses a static vector (or several vectors clustered via K-Means) representing the user's interests. For context-aware search, a **Session Vector** must be created that temporarily "masks" or "blends" with this static vector.  
When the user provides a repo URL (e.g., https://github.com/huggingface/transformers) or a category (e.g., "Zero-Knowledge Proofs"), the system should follow these steps:

1. **Reference Extraction:**  
   * **Repo Input:** The target repo's README.md, description, and topics data are fetched. This text is passed through the sentence-transformers (all-MiniLM-L6-v2) model to create a **Reference Vector (V\_{ref})**.  
   * **Category/Text Input:** A definition entered by the user, such as "Zero-Knowledge Proofs applied to blockchain privacy," is directly vectorized.  
2. **Vector Projection:** When the system collects candidate repos from GitHub, it now compares the vectors of these candidates (V\_{cand}) not with the general user profile, but with this new V\_{ref}.This way, even if the user's general interest is "Web Development," "Cryptography" libraries sought in that session will score higher than web frameworks and pass the filter.

### **3.2 Context-Injected Task Structure**

This feature reduces the Hunter class's dependency on strategy.json in the code. Instead, every search job carries its own context.

| Feature | Standard Search (Current) | Context Search (Proposed) |
| :---- | :---- | :---- |
| **Target** | General User Profile (Star Average) | Specific Repo or Topic (Session Context) |
| **Input** | strategy.json (Keywords) | Target URL or Context String |
| **Filtering** | Similarity \> 0.4 with Profile Vector | Similarity \> 0.6 with Reference Vector (Stricter) |
| **Goal** | "Find me anything I might like" | "Find me things exactly like *this*" |

This structure allows the user to make complex (cross-modal) queries like "Find me repos that look like React but are written in Rust." Here, "React" provides the reference vector, while "Rust" acts as a Hard Filter.

## **Section 4: Asynchronous 'Task Queue' Architecture**

The user's demand to "process existing data instead of stopping when hitting API limits" mandates a shift from a **Blocking** structure to an **Event-Driven** structure. This is possible with Python's asyncio library and a persistent queue system.

### **4.1 Producer-Consumer Design**

We will separate the system from a single loop into three independent "Worker" groups connected by queues. These workers operate at different speeds and do not block each other.

1. **The Scout (Producer):**  
   * **Task:** Searches on the GitHub API (Metadata Search). Only finds repo IDs, URLs, and basic metadata.  
   * **Speed:** High. GitHub Search API limit (30 requests/minute).  
   * **Output:** Pushes raw repo candidates to the DiscoveryQueue.  
   * **Constraint Behavior:** If Search API limit is hit, it sleeps, but other workers continue working.  
2. **The Fetcher (Collector/Intermediate Consumer):**  
   * **Input:** DiscoveryQueue.  
   * **Task:** Goes to the details of the repo taken from the queue, downloads the README.md file (Raw Content).  
   * **Speed:** Very High. GitHub Core API or Raw User Content (5000 requests/hour or unlimited).  
   * **Output:** Pushes "enriched" data packages to the AnalysisQueue.  
3. **The Processor (Processor/Final Consumer):**  
   * **Input:** AnalysisQueue.  
   * **Task:**  
     * **LocalBrain:** Calculates vectors on the downloaded README.  
     * **CloudBrain:** Sends selected ones to Gemini API.  
     * **Storage:** Writes results to the database.  
   * **Speed:** Dependent on CPU and Gemini API limits.  
   * **Feature:** This layer is independent of the GitHub API. Even if the Scout sleeps due to limits, the Processor can continue processing hundreds of repos accumulated in the queue for hours. This is the mechanism for "working instead of stopping."

### **4.2 Queue Persistence and Resilience**

In-Memory queues (asyncio.Queue) are lost when the program closes. For long-running scans, a "Persistent Queue" is essential. An SQLite database is an excellent storage space for these queues.  
**Proposed Database Schema (Queue Table):**

| Column | Type | Description |
| :---- | :---- | :---- |
| task\_id | UUID | Unique identifier for the task. |
| task\_type | ENUM | 'search', 'fetch\_readme', 'analyze\_llm'. |
| payload | JSON | Task data (e.g., Date range to search or Repo ID). |
| priority | INT | Priority order (User specific requests are high priority). |
| status | ENUM | 'pending', 'processing', 'failed', 'completed'. |
| retry\_count | INT | How many times it has been retried in case of error. |

Thanks to this structure, even if the user closes the program with Ctrl+C, the system does not forget "where it left off" upon the next launch. If search tasks are finished but analyze tasks are half-done, it starts by only analyzing.

### **4.3 Smart Rate Limiting**

Instead of a simple time.sleep(60), the system needs a reactive "Sentinel" module that reads HTTP headers.

* X-RateLimit-Remaining: Remaining allowance.  
* X-RateLimit-Reset: UNIX timestamp when the quota resets.

**Algorithm:**

1. Read these headers in every API response.  
2. If Remaining \< 5 (Safety margin):  
   * Calculate Reset Time \- Current Time.  
   * Stop only the relevant worker (e.g., Scout) with await asyncio.sleep(duration).  
   * Log: "Scout waiting for ammo (45 sec). Fetcher and Processor continuing."  
   * Meanwhile, other asynchronous tasks (Processor) continue to use the CPU.

## **Section 5: Recursive Date Slicing Algorithm**

The most definitive solution to the user's "1000 result limit" and "seeing the same results constantly" problem is slicing time. The GitHub API allows querying repositories created within a specific date range (created:2024-01-01..2024-02-01).

### **5.1 Logic of the Algorithm**

The basic assumption is: The number of repos uploaded to GitHub in any given time interval is finite. If there are more than 1,000 repos in an interval, splitting this interval in two reduces the number of repos in both halves. Repeating this process until the repo count in each piece drops below 1,000 theoretically allows for lossless fetching of *all* repos.  
**Algorithm Steps:**

1. **Start:** A wide time range (e.g., 2023-01-01 to Today) and a query (topic:python) are determined.  
2. **Probe:** A "Metadata Request" (usually page 1\) is sent to the API for this date range, and the total\_count value is checked.  
3. **Decision Mechanism:**  
   * **Case A (Safe Zone):** total\_count \<= 1000\.  
     * This interval is "clean". All repos are fetched using Pagination (Page 1 to 10).  
   * **Case B (Overflow Zone):** total\_count \> 1000\.  
     * This interval is "dirty". API does not provide results after 1,000.  
     * **Action (Split):** The time interval is split exactly in half.  
       * Left Interval: Start \-\> Midpoint  
       * Right Interval: Midpoint \-\> End  
     * These two new sub-intervals are added as new discovery tasks to the **Task Queue**.  
4. **Recursion:** Workers pick these new, smaller intervals from the queue and return to step 2\.

### **5.2 Density Anomalies and Precision**

In some cases (e.g., a bot attack or a very popular hackathon day), there might be more than 1,000 repos even in a 1-hour slice. The algorithm can go down to second-level precision (YYYY-MM-DDTHH:MM:SSZ). If there are still more than 1,000 repos in a 1-second slice (theoretically possible, practically rare), the system should activate a second "slicing dimension": **Size Slicing**. Keeping the date range fixed, it attempts to bypass the 1,000 limit with file size filters like size:0..500, size:501..1000.

### **5.3 Continuity and State Tracking**

This algorithm is stored in the task\_queue table in the database as "Date Ranges to Process." When the program is closed and reopened, it knows which date range it last split and continues scanning that microscopic time slice from where it left off. This creates an "infinite" scanning loop and ensures no repo is missed.

## **6\. Development Plan and Roadmap**

Below is a step-by-step implementation plan to bring this architecture to life.

### **Phase 1: Infrastructure and Asynchronous Transformation (Day 1-2)**

In this phase, the synchronous structure (blocking I/O) of the code will be completely converted to an asynchronous structure.

* **Library Update:** Add aiohttp (HTTP client), aiosqlite (Async DB), and tenacity (Retry mechanism) to requirements.txt.  
* **Database Migration:** storage.py will be rewritten to use aiosqlite. The tasks table will be created.  
* **Rate Limiter:** RateLimitMonitor class will be integrated into the aiohttp session and will track headers.

### **Phase 2: Task Queue and Worker Loops (Day 3-4)**

* **Queue Manager:** SQLite-based, priority queue system (TaskQueue class) will be coded.  
* **Worker Separation:** Instead of a single search\_and\_process function, three separate async functions named scout\_worker(), fetch\_worker(), and brain\_worker() will be written.  
* **Orchestrator:** cli.py will start and manage these workers using asyncio.gather().

### **Phase 3: Recursive Date Slicing Engine (Day 5-6)**

* **Algorithm Integration:** Add recursive\_date\_search(query, start, end) method to Hunter class.  
* **Splitting Logic:** In cases where total\_count \> 1000, logic will be established to split the time interval using pendulum or datetime libraries and push it back to the queue.  
* **Test:** Test with a dense keyword like "machine learning" and observe if the system automatically descends to day/hour-based intervals.

### **Phase 4: Context Awareness and Final Integration (Day 7\)**

* **Context API:** Add a new command to CLI: tune focus \--url \<repo\_url\> or tune focus \--topic "subject".  
* **Embedding Override:** Update brain.py so that if a "Focus" is defined, it ignores the general user profile in the database and uses the instantaneously created vector.

## **7\. Conclusion and Recommendations**

The architecture proposed in this report will transform the github-tuner project from a simple data collection tool into an intelligence platform capable of processing data at an industrial scale. Specifically, the **Recursive Date Slicing** algorithm will eliminate data loss by overcoming GitHub's API restrictions with mathematical precision. The **Asynchronous Task Queue** will optimize resource usage, turning the "Chill Mode" philosophy into a technical reality.  
**Final Recommendation:** It is critical that you start development from Phase 1 (Infrastructure). Without laying the asynchronous foundation, managing the thousands of HTTP requests generated by the date slicing algorithm could lead to system deadlocks. With this plan, you will possess a system far more capable and personalized than paid tools on the market (e.g., Greptile, Quivr) for both your own projects and collaborative work with your friend.

#### **Alıntılanan çalışmalar**

1\. Search | GitHub API \- LFE Documentation, https://docs2.lfe.io/v3/search/ 2\. github search limit results \- Stack Overflow, https://stackoverflow.com/questions/37602893/github-search-limit-results 3\. Mastering Asynchronous Queues in Python: Concurrency Made Easy with asyncio | by Basant C. | Medium, https://medium.com/@caring\_smitten\_gerbil\_914/mastering-asynchronous-queues-in-python-concurrency-made-easy-with-asyncio-878566ef9d7d 4\. How to Use asyncio Effectively in Python for I/O-Bound Workloads \- OneUptime, https://oneuptime.com/blog/post/2025-01-06-python-asyncio-io-bound/view 5\. GitHub Assistant: Interact with your GitHub repository using RAG and Elasticsearch, https://www.elastic.co/search-labs/blog/github-rag-elasticsearch 6\. What was that commit? Searching GitHub with OpenAI embeddings \- Blog \- Sequin, https://blog.sequin.io/what-was-that-commit-searching-github-with-openai-embeddings/ 7\. Vector embeddings | OpenAI API, https://platform.openai.com/docs/guides/embeddings 8\. Asyncio Queues: Producer-Consumer \- Tutorial | Krython, https://krython.com/tutorial/python/asyncio-queues-producer-consumer/ 9\. Rate limits and query limits for the GraphQL API \- GitHub Docs, https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api 10\. Rate limits for the REST API \- GitHub Docs, https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api 11\. There is a limit of 1000 results per search. · Issue \#824 \- GitHub, https://github.com/PyGithub/PyGithub/issues/824 12\. How to get more than 1000 search results with API Github \- Stack Overflow, https://stackoverflow.com/questions/61810553/how-to-get-more-than-1000-search-results-with-api-github 13\. How many files per repository folder? Is 1000 the max? I got an error on my repo saying 'Sorry, we had to truncate this directory to 1000 files. 170 entries were omitted from the list' at the home page? · community · Discussion \#136892 \- GitHub, https://github.com/orgs/community/discussions/136892
# Algorithmic Complexity & Theoretical Foundations

This document provides formal time and space complexity analyses for all core algorithmic subsystems within the **Intelligent SQL Assistant (Trust Engine)** platform.

---

## 📊 Algorithmic Complexity Summary Matrix

| Subsystem / Algorithm | Time Complexity (Average) | Time Complexity (Worst-Case) | Space Complexity | Primary Data Structure |
| :--- | :--- | :--- | :--- | :--- |
| **Topological Pipeline Sort (Kahn's)** | $O(V + E)$ | $O(V + E)$ | $O(V + E)$ | Adjacency List + `collections.deque` |
| **Bitmask DP Join Optimizer ($N \le 8$)** | $O(3^N)$ | $O(3^N)$ | $O(2^N)$ | Integer Bitmask DP Array / Hash Map |
| **Greedy Join Optimizer ($N > 8$)** | $O(N^2 \log N)$ | $O(N^2 \log N)$ | $O(N^2)$ | Min-Heap Priority Queue (`heapq`) |
| **AST Policy Verification & Rewrite** | $O(N_{\text{nodes}})$ | $O(N_{\text{nodes}})$ | $O(H_{\text{AST}})$ | SQLglot AST Tree Hierarchy |
| **Multiset Tuple Equality Comparator** | $O(R \log R \cdot C)$ | $O(R \log R \cdot C)$ | $O(R \cdot C)$ | Canonical Hash Set + Sorted Tuples |
| **Sliding-Window Rate Limiter** | $O(\log K + M)$ | $O(\log K + M)$ | $O(K)$ | Redis Sorted Set (ZSET) |
| **Distributed Token Revocation** | $O(1)$ | $O(1)$ | $O(1)$ per token | In-Memory Hash Set + Redis Key-Value |

---

## 1. Kahn's Algorithm & Topological Pipeline Sorting

### Implementation
Located in [`dag_validator.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/services/dag_validator.py). Validates multi-step compound query plans and sub-query dependencies.

### Formulation
- **Vertices ($V$)**: Analytical sub-tasks or CTE execution steps.
- **Edges ($E$)**: Directed data-flow dependencies ($u \to v$).
- **Queue Initialization**: Finds all vertices with $\text{in\_degree}(u) = 0$.
- **Queue Traversal**: Uses `collections.deque.popleft()` for guaranteed $O(1)$ queue extractions.

### Complexity Analysis
1. **Adjacency & Degree Graph Construction**: Iterating over all edges takes $O(E)$ time and $O(V + E)$ space.
2. **In-Degree Initialization**: Inspecting all $V$ nodes takes $O(V)$ time.
3. **Queue Processing**:
   - Each vertex $u$ is enqueued and dequeued exactly once: $V \times O(1) = O(V)$.
   - Each directed edge $(u, v)$ is traversed exactly once to decrement $\text{in\_degree}(v)$: $E \times O(1) = O(E)$.
4. **Cycle Detection**: If the processed node count $< |V|$, a directed cycle is detected in $O(1)$ comparison.

$$\text{Total Time Complexity} = O(V + E)$$
$$\text{Total Auxiliary Space} = O(V + E)$$

---

## 2. Cost-Based Physical Join Order Optimizer

### Implementation
Located in [`join_optimizer.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/services/join_optimizer.py).

### 2.1 Exact Bitmask Dynamic Programming ($N \le 8$)

For a query joining $N$ relations, every non-empty subset of relations is represented as an integer bitmask $S \in [1, 2^N - 1]$.

#### State Transition Formulation
For any subset $S \subseteq \{1, \dots, N\}$ with $|S| \ge 2$:
$$\text{DP}[S] = \min_{\substack{s_1 \subset S \\ s_2 = S \setminus s_1 \\ s_1 \text{ joins } s_2}} \left( \text{DP}[s_1] + \text{DP}[s_2] + \text{JoinCost}(s_1, s_2) \right)$$

#### Submask Enumeration
Submasks $s_1 \subset S$ are enumerated efficiently using bitwise subtraction:
```python
s1 = (S - 1) & S
while s1 > 0:
    s2 = S ^ s1
    # Evaluate valid join partition...
    s1 = (s1 - 1) & S
```

#### Complexity Derivation
The total number of submask iterations across all $2^N$ masks is given by the Binomial Theorem:
$$\sum_{k=0}^N \binom{N}{k} 2^k = (1 + 2)^N = 3^N$$

For $N = 4$: $3^4 = 81$ operations.  
For $N = 8$: $3^8 = 6,561$ operations ($< 1\text{ms}$ compute).

$$\text{Time Complexity} = O(3^N)$$
$$\text{Space Complexity} = O(2^N) \text{ DP table entries}$$

---

### 2.2 Greedy Priority Queue Fallback ($N > 8$)

When $N > 8$, exact dynamic programming becomes computationally expensive ($3^{10} = 59,049$, $3^{16} \approx 4.3 \times 10^7$). The optimizer switches to a greedy minimum-selectivity heuristic planner:

1. Computes all candidate pairwise join edges ($O(N^2)$).
2. Pushes edges into a min-heap priority queue ordered by $\text{Cost}(\text{Join}(u, v))$.
3. Repeatedly extracts the cheapest join pair and merges the sub-plans until a single unified tree remains.

$$\text{Time Complexity} = O(N^2 \log N)$$
$$\text{Space Complexity} = O(N^2)$$

---

### 2.3 Physical Operator Cost Model (Selinger / System-R)

1. **Sequential Scan**:
   $$C_{\text{seq}} = N_{\text{pages}} \cdot 1.0 + N_{\text{tuples}} \cdot 0.01$$
2. **Index Scan**:
   $$C_{\text{idx}} = N_{\text{pages}} \cdot \text{selectivity} \cdot 4.0 + N_{\text{tuples}} \cdot \text{selectivity} \cdot 0.005$$
3. **Hash Join**:
   $$C_{\text{hash}} = C_{\text{left}} + C_{\text{right}} + |R_{\text{left}}| \cdot 0.02 + |R_{\text{right}}| \cdot 0.01$$
4. **Sort-Merge Join**:
   $$C_{\text{merge}} = C_{\text{left}} + C_{\text{right}} + |R_{\text{left}}| \log_2 |R_{\text{left}}| \cdot 0.01 + |R_{\text{right}}| \log_2 |R_{\text{right}}| \cdot 0.01 + (|R_{\text{left}}| + |R_{\text{right}}|) \cdot 0.005$$
5. **Nested Loop Join**:
   $$C_{\text{nested}} = C_{\text{left}} + |R_{\text{left}}| \cdot C_{\text{right\_page\_fetch}} + (|R_{\text{left}}| \cdot |R_{\text{right}}|) \cdot 0.01$$

---

## 3. Deterministic AST Policy & Security Engine

### Implementation
Located in [`sql_parser.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/services/sql_parser.py) and [`policy_engine.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/services/policy_engine.py).

### Complexity Analysis
1. **AST Parsing**: SQLglot performs recursive descent LL(k) parsing on the SQL token stream: $O(N_{\text{tokens}})$.
2. **AST Visitor Traversal**: Visits every AST node $n \in \text{AST}$ exactly once: $O(N_{\text{nodes}})$.
3. **Identifier Resolution**: Table and column lookups against pre-cached role policy hash maps take $O(1)$ per identifier.
4. **Row-Filter Predicate Injection**: AST root transformation is performed in $O(1)$ tree pointer manipulation.

$$\text{Total Time Complexity} = O(N_{\text{nodes}} + T + C)$$
$$\text{Total Space Complexity} = O(H_{\text{AST}}) \text{ call stack depth}$$

---

## 4. Multiset Tuple-Equality Result Verification

### Implementation
Located in [`evaluation_lab.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/services/evaluation_lab.py).

### Formulation
Evaluates true semantic execution equality between candidate result set $R_{\text{cand}}$ and reference ground-truth set $R_{\text{true}}$.

1. **Column Name Normalization**: Maps dictionary keys to canonical lowercase sorted tuples: $O(R \cdot C)$.
2. **Numerical Float Rounding**: Rounds floating-point numbers to 4 decimal places ($10^{-4}$ tolerance): $O(R \cdot C)$.
3. **Multiset Sorting**: Canonicalizes rows into sorted tuple arrays:
   $$O(R \log R \cdot C)$$
4. **Element-wise Equality**: Compares sorted row arrays: $O(R \cdot C)$.

$$\text{Total Time Complexity} = O(R \log R \cdot C)$$
$$\text{Total Space Complexity} = O(R \cdot C)$$

---

## 5. Distributed Sliding-Window Rate Limiter

### Implementation
Located in [`redis_client.py`](file:///d:/Python/Data%20sets%20by%20campusx/Intelligent_SQL_Assistant/backend/app/core/redis_client.py).

### Formulation
Uses Redis Sorted Sets (ZSET) where each request score and member is the Unix timestamp $\tau$.

1. `ZREMRANGEBYSCORE(key, 0, now - window)`: Removes $M$ expired elements in $O(\log K + M)$.
2. `ZCARD(key)`: Counts active timestamps in current window in $O(1)$.
3. `ZADD(key, now, now)`: Inserts current request timestamp in $O(\log K)$.
4. `EXPIRE(key, window + 5)`: Refreshes key TTL in $O(1)$.

$$\text{Total Time Complexity} = O(\log K + M)$$
$$\text{Total Space Complexity} = O(K) \text{ timestamps per active window}$$

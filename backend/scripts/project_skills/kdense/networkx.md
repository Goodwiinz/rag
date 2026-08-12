---
name: networkx
description: Compute structural graph metrics with NetworkX in the sandboxed code tool — centrality, shortest paths, community detection, connectivity. For the project's own knowledge graph, use the graph tools instead; see this skill's notes.
---

# NetworkX

Analyze the structure of a graph the researcher has constructed or exported: centrality, paths, communities, and connectivity, computed with NetworkX. All computation runs through `execute_code` (sandboxed Python; NetworkX is not preinstalled, so pass it via the `packages` argument alongside numpy, pandas, and matplotlib, which are already available).

Adapted from K-Dense scientific-agent-skills (MIT license).

## Boundary: this skill versus the project's knowledge graph

NOUS has a first-class knowledge graph, queried directly with `search_knowledge_graph`, `explore_entity_neighborhood`, `find_entity_paths`, `extract_entities`, and `get_graph_stats`. Use those tools whenever the question is about the project's own graph: what entities exist, how two entities relate, what neighbors an entity has, or overall graph statistics — they operate on the live, tenant-scoped store and are always the right first stop for that graph.

Use this skill's NetworkX workflow instead when the researcher needs a structural metric those tools do not compute (betweenness centrality, community detection, a custom shortest-path weighting, a synthetic or exported network) or is working with a graph that did not come from `search_knowledge_graph` at all — a citation network built from search results, a collaboration network assembled from document metadata, or any graph loaded from an external file. A common pattern: pull entities and relationships from the knowledge graph tools, load them into a NetworkX graph inside `execute_code`, then compute the metric the graph tools do not expose.

## When to apply

- Computing centrality measures (degree, betweenness, closeness, eigenvector, PageRank) on a constructed or exported graph
- Community detection or clustering on a network
- Shortest-path or connectivity analysis with custom edge weights
- Building or analyzing synthetic networks (random, scale-free, small-world) for methodology or comparison
- Reading a graph from an external format (edge list, GraphML, adjacency data) and computing metrics on it

## Workflow

1. Choose the graph type deliberately: `Graph` for undirected single edges, `DiGraph` for directed, `MultiGraph`/`MultiDiGraph` when multiple edges can exist between the same pair of nodes — the wrong type silently drops information (an undirected graph loses direction, a simple graph collapses parallel edges).
2. Build the graph with nodes and edges carrying the attributes the analysis needs (weights, types, timestamps) rather than adding them after the fact.
3. Check basic structure first: node and edge counts, `nx.is_connected` (or weakly/strongly connected for directed graphs), and the largest connected component — many algorithms assume connectivity and behave oddly or raise on a disconnected graph.
4. Run the algorithm matched to the question, on the appropriate connected component if the graph is disconnected.
5. Interpret results against the graph's structure, not just the raw numbers — a node with high degree in a sparse graph is more distinctive than the same degree in a dense one.

## Core algorithms

- Shortest paths: `nx.shortest_path` and `nx.shortest_path_length`, weighted by an edge attribute when distance is not simply hop count; `nx.all_shortest_paths` when ties matter.
- Centrality: degree centrality for local connectivity, betweenness centrality for brokerage/bridging position, closeness centrality for average reach, eigenvector centrality or PageRank for influence that accounts for neighbors' importance — pick based on what "important" means for the question, since these routinely disagree on the same graph.
- Community detection: `community.greedy_modularity_communities` as a reasonable default; label propagation or the Louvain-style methods available in NetworkX for larger graphs where modularity optimization is slow. Report modularity score alongside the partition so the community structure's strength is stated, not assumed.
- Connectivity: `nx.connected_components` (undirected) or `nx.strongly_connected_components`/`nx.weakly_connected_components` (directed); articulation points and bridges to find structurally fragile nodes and edges.
- Clustering and transitivity: `nx.clustering` per node and `nx.transitivity` globally, for how tightly a node's neighbors interconnect.
- Network generation for comparison or null models: `nx.erdos_renyi_graph` (random), `nx.barabasi_albert_graph` (scale-free), `nx.watts_strogatz_graph` (small-world) — useful as a baseline to judge whether an observed metric on the real graph is structurally unusual.

## Reporting

Record with `create_project_note`: the graph's source (constructed from what data, or exported from the knowledge graph via which tool calls), node and edge counts, the graph type and why it was chosen, the algorithms run and their parameters, and the resulting metrics with brief interpretation. Plots produced with `execute_code` should use a layout matched to the graph's size (`spring_layout` for small-to-medium graphs, degree-sorted or community-colored layouts for larger ones) and should label or color nodes by the attribute the analysis is about, not leave them undifferentiated.

## Pitfalls

1. Reaching for NetworkX to answer a question about the project's own knowledge graph — `search_knowledge_graph`, `explore_entity_neighborhood`, `find_entity_paths`, and `get_graph_stats` already answer that directly and stay tenant-scoped; hand-rolling the same query in NetworkX means working from a stale or partial export.
2. Wrong graph type — an undirected `Graph` used for data that is actually directed erases meaningful asymmetry (who cites whom, who follows whom).
3. Running a connectivity-assuming algorithm on a disconnected graph without first restricting to a component, producing an error or a misleading result.
4. Comparing centrality values across graphs of different sizes without normalizing — raw betweenness or degree is not comparable across networks with different node counts.
5. Treating a single community-detection run as ground truth — these algorithms are stochastic or resolution-dependent; report the modularity score and note sensitivity to the method chosen.
6. Ignoring edge weights when the question is about distance or strength, defaulting to unweighted hop count by omission.

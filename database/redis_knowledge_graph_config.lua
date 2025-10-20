-- Redis Configuration for Knowledge Graph Caching and Real-time Updates
-- This script configures Redis for optimal performance with graph data

-- Redis configuration
redis.config_set('maxmemory', '4gb')
redis.config_set('maxmemory-policy', 'allkeys-lru')
redis.config_set('save', '900 1 300 10 60 10000')

-- Knowledge Graph Data Structures Configuration

-- 1. Entity Centrality Scores Cache
-- Keys: entity:centrality:{entity_id}:{metric_type}
-- Type: String (float value)
-- TTL: 3600 seconds (1 hour)
-- Description: Caches computed centrality metrics for entities

-- Example: entity:centrality:12345:degree = 0.85
-- Example: entity:centrality:12345:pagerank = 0.043
-- Example: entity:centrality:12345:betweenness = 0.012

-- 2. Graph Layout Positions Cache
-- Keys: graph:layout:{graph_id}:{algorithm}
-- Type: Hash
-- TTL: 7200 seconds (2 hours)
-- Description: Caches computed layout positions for graph visualization

-- Hash fields for each entity:
-- {entity_id}_x = 100.5
-- {entity_id}_y = 200.3
-- {entity_id}_level = 1
-- {entity_id}_cluster = "cluster_1"

-- 3. Shortest Path Cache
-- Keys: paths:shortest:{source_id}:{target_id}
-- Type: List (ordered list of entity IDs)
-- TTL: 1800 seconds (30 minutes)
-- Description: Caches computed shortest paths between entities

-- Example: paths:shortest:12345:67890 = ["12345", "23456", "34567", "67890"]

-- 4. Community Detection Results
-- Keys: communities:{organization_id}:{algorithm}
-- Type: Hash
-- TTL: 86400 seconds (24 hours)
-- Description: Caches community detection results

-- Hash fields:
-- community_{id} = JSON array of entity IDs
-- community_count = total number of communities
-- modularity_score = network modularity value
-- algorithm = algorithm used
-- computed_at = timestamp

-- 5. Real-time Graph Statistics
-- Keys: stats:graph:{organization_id}:realtime
-- Type: Hash
-- TTL: 300 seconds (5 minutes)
-- Description: Real-time graph statistics for dashboards

-- Hash fields:
-- total_nodes = 1234
-- total_edges = 5678
-- avg_degree = 4.2
-- connected_components = 3
-- largest_component_size = 1200
-- graph_density = 0.0034
-- avg_confidence = 0.82
-- last_updated = 1640995200

-- 6. User-specific View Cache
-- Keys: view:graph:{user_id}:{view_hash}
-- Type: String (JSON)
-- TTL: 1800 seconds (30 minutes)
-- Description: Caches user's personalized graph view with filters and layout

-- JSON structure:
-- {
--   "nodes": [...],
--   "edges": [...],
--   "layout": {"algorithm": "force", "positions": {...}},
--   "filters": {"entity_types": ["person"], "confidence_threshold": 0.7},
--   "computed_at": 1640995200,
--   "expires_at": 1640997000
-- }

-- 7. Computation Job Status
-- Keys: job:graph:{job_id}
-- Type: Hash
-- TTL: 86400 seconds (24 hours)
-- Description: Tracks status of background graph computation jobs

-- Hash fields:
-- status = "running" | "completed" | "failed"
-- progress = 45
-- total_steps = 100
-- current_step = "Computing centrality metrics"
-- started_at = 1640995200
-- estimated_completion = 1640999800
-- result_location = "s3://results/job_123.json"
-- error_message = null
-- computation_time_ms = 12345

-- 8. Entity Neighborhood Cache
-- Keys: neighborhood:{entity_id}:{depth}:{organization_id}
-- Type: String (JSON)
-- TTL: 3600 seconds (1 hour)
-- Description: Caches computed entity neighborhoods for fast access

-- JSON structure:
-- {
--   "central_entity": {...},
--   "entities": [...],
--   "relationships": [...],
--   "total_nodes": 25,
--   "total_edges": 40,
--   "depth_reached": 2,
--   "computed_at": 1640995200,
--   "computation_time_ms": 234
-- }

-- 9. Graph Insights Cache
-- Keys: insights:{organization_id}:{category}
-- Type: String (JSON)
-- TTL: 21600 seconds (6 hours)
-- Description: Caches AI-generated graph insights

-- JSON structure:
-- {
--   "insights": [
--     {
--       "id": "insight_123",
--       "type": "quality_issue",
--       "severity": "high",
--       "title": "Low confidence entities detected",
--       "description": "15 entities have confidence below 0.5",
--       "affected_entities": [...],
--       "recommendations": [...],
--       "impact_score": 0.8,
--       "generated_at": 1640995200
--     }
--   ],
--   "generated_at": 1640995200,
--   "expires_at": 1641016800
-- }

-- 10. Entity Similarity Cache
-- Keys: similarity:entity:{entity_id}:{limit}
-- Type: List (of entity IDs with scores)
-- TTL: 7200 seconds (2 hours)
-- Description: Caches similar entities for quick recommendations

-- List items: "entity_id:score" (e.g., "67890:0.92")

-- 11. Graph Algorithm Parameters Cache
-- Keys: params:algorithm:{algorithm_name}
-- Type: Hash
-- TTL: 86400 seconds (24 hours)
-- Description: Caches optimal parameters for graph algorithms

-- Hash fields:
-- default_resolution = 1.0
-- min_community_size = 5
-- damping_factor = 0.85
-- max_iterations = 100
-- convergence_threshold = 0.0001

-- 12. User Interaction Analytics
-- Keys: analytics:user:{user_id}:interactions
-- Type: Sorted Set
-- TTL: 604800 seconds (7 days)
-- Description: Tracks user interactions for analytics

-- Score: timestamp, Member: interaction_data JSON
-- Example: 1640995200 = {"type": "entity_click", "entity_id": "12345", "context": {...}}

-- Pub/Sub Channels for Real-time Updates

-- 1. Organization-wide Updates
-- Channel: channel:graph:updates:{organization_id}
-- Messages:
-- {
--   "type": "entity_created",
--   "entity_id": "12345",
--   "entity_type": "person",
--   "timestamp": 1640995200,
--   "organization_id": "org_123"
-- }

-- 2. Entity-specific Updates
-- Channel: channel:entity:updated:{organization_id}
-- Channel: channel:entity:created:{organization_id}
-- Channel: channel:entity:deleted:{organization_id}

-- 3. Relationship Updates
-- Channel: channel:relationship:created:{organization_id}
-- Channel: channel:relationship:updated:{organization_id}
-- Channel: channel:relationship:deleted:{organization_id}

-- 4. Computation Updates
-- Channel: channel:computation:started:{organization_id}
-- Channel: channel:computation:progress:{organization_id}
-- Channel: channel:computation:completed:{organization_id}
-- Channel: channel:computation:failed:{organization_id}

-- 5. Analytics Updates
-- Channel: channel:analytics:updated:{organization_id}

-- Redis Functions for Graph Operations

-- Function to get or compute entity centrality
redis.create_function('get_entity_centrality', {
  keys = {'entity_id', 'metric_type'},
  values = {'organization_id', 'compute_if_missing'},
  body = [[
    local cache_key = 'entity:centrality:' .. KEYS[1] .. ':' .. KEYS[2]
    local cached_value = redis.call('GET', cache_key)

    if cached_value then
      return cached_value
    end

    if ARGV[2] == 'true' then
      -- Trigger background computation
      redis.call('PUBLISH', 'channel:computation:needed:' .. ARGV[1],
        json.encode({
          type = 'centrality_computation',
          entity_id = KEYS[1],
          metric_type = KEYS[2],
          organization_id = ARGV[1]
        })
      )
      return 'computing'
    else
      return nil
    end
  ]]
})

-- Function to cache graph layout
redis.create_function('cache_graph_layout', {
  keys = {'graph_id', 'algorithm'},
  values = {'layout_data', 'ttl'},
  body = [[
    local cache_key = 'graph:layout:' .. KEYS[1] .. ':' .. KEYS[2]
    local ttl = tonumber(ARGV[2]) or 7200

    -- Parse layout data and store as hash
    local layout = json.decode(ARGV[1])
    for entity_id, position in pairs(layout.positions) do
      redis.call('HSET', cache_key, entity_id .. '_x', position.x)
      redis.call('HSET', cache_key, entity_id .. '_y', position.y)
      if position.level then
        redis.call('HSET', cache_key, entity_id .. '_level', position.level)
      end
      if position.cluster then
        redis.call('HSET', cache_key, entity_id .. '_cluster', position.cluster)
      end
    end

    -- Set metadata
    redis.call('HSET', cache_key, 'metadata', json.encode(layout.metadata))
    redis.call('EXPIRE', cache_key, ttl)

    return 'cached'
  ]]
})

-- Function to update real-time statistics
redis.create_function('update_graph_stats', {
  keys = {'organization_id'},
  values = {'stats_data'},
  body = [[
    local stats_key = 'stats:graph:' .. KEYS[1] .. ':realtime'
    local stats = json.decode(ARGV[1])

    -- Update statistics
    for key, value in pairs(stats) do
      redis.call('HSET', stats_key, key, tostring(value))
    end

    redis.call('HSET', stats_key, 'last_updated', tostring(redis.call('TIME')[1]))
    redis.call('EXPIRE', stats_key, 300)

    -- Publish update
    redis.call('PUBLISH', 'channel:analytics:updated:' .. KEYS[1],
      json.encode({
        type = 'stats_updated',
        organization_id = KEYS[1],
        stats = stats,
        timestamp = redis.call('TIME')[1]
      })
    )

    return 'updated'
  ]]
})

-- Function to invalidate related caches
redis.create_function('invalidate_entity_caches', {
  keys = {'entity_id', 'organization_id'},
  values = {},
  body = [[
    local entity_id = KEYS[1]
    local org_id = KEYS[2]

    -- Invalidate centrality caches
    local metrics = {'degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank'}
    for _, metric in ipairs(metrics) do
      redis.call('DEL', 'entity:centrality:' .. entity_id .. ':' .. metric)
    end

    -- Invalidate similarity cache
    local pattern = 'similarity:entity:' .. entity_id .. ':*'
    local keys = redis.call('KEYS', pattern)
    for _, key in ipairs(keys) do
      redis.call('DEL', key)
    end

    -- Invalidate neighborhood caches
    local neighborhood_pattern = 'neighborhood:' .. entity_id .. ':*'
    local neighborhood_keys = redis.call('KEYS', neighborhood_pattern)
    for _, key in ipairs(neighborhood_keys) do
      redis.call('DEL', key)
    end

    -- Publish update
    redis.call('PUBLISH', 'channel:entity:updated:' .. org_id,
      json.encode({
        type = 'entity_updated',
        entity_id = entity_id,
        organization_id = org_id,
        timestamp = redis.call('TIME')[1]
      })
    )

    return 'invalidated'
  ]]
})

-- Lua script for batch cache warming
local function warm_entity_caches(entity_ids, organization_id)
  for _, entity_id in ipairs(entity_ids) do
    -- Check and warm centrality caches
    local metrics = {'degree', 'pagerank', 'betweenness'}
    for _, metric in ipairs(metrics) do
      local cache_key = 'entity:centrality:' .. entity_id .. ':' .. metric
      if not redis.call('EXISTS', cache_key) then
        -- Trigger background computation
        redis.call('PUBLISH', 'channel:computation:needed:' .. organization_id,
          json.encode({
            type = 'centrality_computation',
            entity_id = entity_id,
            metric_type = metric,
            organization_id = organization_id
          })
        )
      end
    end
  end
end

-- Initialize Redis for Knowledge Graph
print("✅ Redis Knowledge Graph Configuration Applied")
print("📊 Data structures configured for graph caching")
print("🔄 Real-time update channels established")
print("⚡ Performance optimizations enabled")
print("🔧 Functions and scripts loaded")
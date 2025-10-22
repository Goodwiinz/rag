import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Data Flow Integrity Validation', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting data flow integrity test on ${browserName}`);

    // Login as admin for full system access
    await helpers.login(TEST_DATA.USERS.ADMIN);
  });

  test.describe('Document Processing Data Flow', () => {
    test('should maintain data integrity through document upload and processing pipeline', async ({ page }) => {
      helpers.logStep('Testing document processing data flow integrity');

      // Step 1: Navigate to document upload
      await helpers.waitAndClick('[data-testid="documents-nav-link"]');
      await helpers.expectElementVisible('[data-testid="document-upload-zone"]');
      helpers.logStep('Navigated to document upload');

      // Step 2: Upload test document
      const testFilePath = './tests/fixtures/files/sample-document.pdf';
      await helpers.uploadFile('[data-testid="file-input"]', testFilePath);
      await helpers.waitAndClick('[data-testid="upload-button"]');

      // Capture upload response data
      const uploadResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/documents/upload') && response.status() === 201
      );
      const uploadData = await uploadResponse.json();
      const documentId = uploadData.id;
      expect(documentId).toBeTruthy();
      helpers.logStep(`Document uploaded with ID: ${documentId}`);

      // Step 3: Monitor processing pipeline
      await helpers.expectElementVisible('[data-testid="processing-status"]');
      await helpers.expectElementVisible('[data-testid="processing-progress"]');

      // Wait for processing to complete
      await helpers.expectElementVisible('[data-testid="processing-complete"]', { timeout: 30000 });
      helpers.logStep('Document processing completed');

      // Step 4: Verify extracted data integrity
      await helpers.waitAndClick('[data-testid="view-document"]');
      await helpers.expectElementVisible('[data-testid="document-details"]');

      // Check document metadata
      const documentTitle = await helpers.getTextContent('[data-testid="document-title"]');
      const documentSize = await helpers.getTextContent('[data-testid="document-size"]');
      const processingTime = await helpers.getTextContent('[data-testid="processing-time"]');

      expect(documentTitle).toBeTruthy();
      expect(documentSize).toBeTruthy();
      expect(processingTime).toBeTruthy();
      helpers.logStep(`Document metadata: ${documentTitle}, ${documentSize}, processed in ${processingTime}`);

      // Step 5: Verify extracted entities
      await helpers.waitAndClick('[data-testid="extracted-entities-tab"]');
      await helpers.expectElementVisible('[data-testid="entities-list"]');

      const entities = page.locator('[data-testid="entity-item"]');
      await expect(entities).toHaveCount.greaterThan(0);

      // Validate entity structure
      for (let i = 0; i < Math.min(await entities.count(), 5); i++) {
        const entity = entities.nth(i);
        await expect(entity.locator('[data-testid="entity-name"]')).toBeVisible();
        await expect(entity.locator('[data-testid="entity-type"]')).toBeVisible();
        await expect(entity.locator('[data-testid="entity-confidence"]')).toBeVisible();
      }
      helpers.logStep(`Extracted ${await entities.count()} entities`);

      // Step 6: Verify knowledge graph integration
      await helpers.waitAndClick('[data-testid="graph-integration-tab"]');
      await helpers.expectElementVisible('[data-testid="graph-nodes"]');

      const graphNodes = page.locator('[data-testid="graph-node"]');
      await expect(graphNodes).toHaveCount.greaterThan(0);
      helpers.logStep(`Created ${await graphNodes.count()} graph nodes`);

      // Step 7: Verify analytics data generation
      await helpers.waitAndClick('[data-testid="analytics-tab"]');
      await helpers.expectElementVisible('[data-testid="document-analytics"]');

      const analyticsMetrics = page.locator('[data-testid="analytics-metric"]');
      await expect(analyticsMetrics).toHaveCount.greaterThan(0);
      helpers.logStep('Document analytics generated');

      // Step 8: End-to-end data validation
      const finalResponse = await page.waitForResponse(response =>
        response.url().includes(`/api/v1/documents/${documentId}`) && response.status() === 200
      );
      const finalData = await finalResponse.json();

      expect(finalData.id).toBe(documentId);
      expect(finalData.status).toBe('processed');
      expect(finalData.entities).toBeDefined();
      expect(finalData.analytics).toBeDefined();
      helpers.logStep('End-to-end data validation passed');
    });

    test('should handle batch document processing with data consistency', async ({ page }) => {
      helpers.logStep('Testing batch document processing data consistency');

      await helpers.waitAndClick('[data-testid="documents-nav-link"]');
      await helpers.waitAndClick('[data-testid="batch-upload-tab"]');
      await helpers.expectElementVisible('[data-testid="batch-upload-zone"]');

      // Step 1: Upload multiple documents
      const testFiles = [
        './tests/fixtures/files/sample-document.pdf',
        './tests/fixtures/files/sample-text.txt',
        './tests/fixtures/files/sample-image.jpg'
      ];

      const documentIds: string[] = [];

      for (const filePath of testFiles) {
        await helpers.uploadFile('[data-testid="batch-file-input"]', filePath);
        await page.waitForTimeout(500);
      }

      await helpers.waitAndClick('[data-testid="start-batch-upload"]');

      // Step 2: Monitor batch processing
      await helpers.expectElementVisible('[data-testid="batch-progress"]');
      await helpers.expectElementVisible('[data-testid="batch-status"]');

      // Capture batch response
      const batchResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/documents/batch') && response.status() === 201
      );
      const batchData = await batchResponse.json();
      expect(batchData.batch_id).toBeTruthy();
      expect(batchData.document_count).toBe(testFiles.length);
      helpers.logStep(`Batch upload initiated: ${batchData.document_count} documents`);

      // Step 3: Wait for batch processing to complete
      await helpers.expectElementVisible('[data-testid="batch-complete"]', { timeout: 60000 });
      helpers.logStep('Batch processing completed');

      // Step 4: Verify all documents were processed consistently
      await helpers.waitAndClick('[data-testid="batch-results"]');
      await helpers.expectElementVisible('[data-testid="batch-results-list"]');

      const resultItems = page.locator('[data-testid="batch-result-item"]');
      await expect(resultItems).toHaveCount(testFiles.length);

      for (let i = 0; i < await resultItems.count(); i++) {
        const item = resultItems.nth(i);
        const docId = await item.getAttribute('data-document-id');
        const status = await helpers.getTextContent(item.locator('[data-testid="processing-status"]'));
        const errorCount = await helpers.getTextContent(item.locator('[data-testid="error-count"]'));

        expect(docId).toBeTruthy();
        expect(status).toBe('completed');
        expect(errorCount).toBe('0');

        documentIds.push(docId!);
      }
      helpers.logStep(`All ${documentIds.length} documents processed successfully`);

      // Step 5: Verify cross-document data consistency
      await helpers.waitAndClick('[data-testid="cross-document-analysis"]');
      await helpers.expectElementVisible('[data-testid="consistency-report"]');

      const consistencyScore = await helpers.getTextContent('[data-testid="consistency-score"]');
      expect(parseFloat(consistencyScore)).toBeGreaterThan(0.9);
      helpers.logStep(`Cross-document consistency score: ${consistencyScore}`);

      // Step 6: Verify batch analytics aggregation
      await helpers.waitAndClick('[data-testid="batch-analytics"]');
      await helpers.expectElementVisible('[data-testid="batch-metrics"]');

      const totalEntities = await helpers.getTextContent('[data-testid="total-entities"]');
      const totalNodes = await helpers.getTextContent('[data-testid="total-nodes"]');
      const totalEdges = await helpers.getTextContent('[data-testid="total-edges"]');

      expect(parseInt(totalEntities)).toBeGreaterThan(0);
      expect(parseInt(totalNodes)).toBeGreaterThan(0);
      expect(parseInt(totalEdges)).toBeGreaterThanOrEqual(0);
      helpers.logStep(`Batch analytics: ${totalEntities} entities, ${totalNodes} nodes, ${totalEdges} edges`);
    });
  });

  test.describe('Knowledge Graph Data Consistency', () => {
    test('should maintain graph data consistency during entity operations', async ({ page }) => {
      helpers.logStep('Testing knowledge graph data consistency');

      // Step 1: Navigate to graph view
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');
      await page.waitForTimeout(3000); // Wait for graph to load

      // Step 2: Get initial graph state
      const initialNodes = await page.locator('[data-testid="graph-node"]').count();
      const initialEdges = await page.locator('[data-testid="graph-edge"]').count();
      helpers.logStep(`Initial graph state: ${initialNodes} nodes, ${initialEdges} edges`);

      // Step 3: Add new entity
      await helpers.waitAndClick('[data-testid="add-entity-button"]');
      await helpers.expectElementVisible('[data-testid="entity-creation-form"]');

      await helpers.fillField('[data-testid="entity-name"]', 'Test Entity E2E');
      await helpers.selectOption('[data-testid="entity-type"]', 'Person');
      await helpers.fillField('[data-testid="entity-description"]', 'Test entity for E2E validation');
      await helpers.waitAndClick('[data-testid="save-entity"]');

      // Capture entity creation response
      const createResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/entities') && response.status() === 201
      );
      const entityData = await createResponse.json();
      const entityId = entityData.id;
      expect(entityId).toBeTruthy();
      helpers.logStep(`Entity created with ID: ${entityId}`);

      // Step 4: Verify graph update
      await page.waitForTimeout(2000);
      const updatedNodes = await page.locator('[data-testid="graph-node"]').count();
      expect(updatedNodes).toBe(initialNodes + 1);
      helpers.logStep(`Graph updated: ${updatedNodes} nodes`);

      // Step 5: Add relationship
      await helpers.waitAndClick('[data-testid="add-relationship-button"]');
      await helpers.expectElementVisible('[data-testid="relationship-creation-form"]');

      await helpers.selectOption('[data-testid="source-entity"]', entityId);
      await helpers.selectOption('[data-testid="target-entity"]', 'Test Organization'); // Assuming this exists
      await helpers.selectOption('[data-testid="relationship-type"]', 'WORKS_FOR');
      await helpers.waitAndClick('[data-testid="save-relationship"]');

      // Capture relationship creation response
      const relResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/relationships') && response.status() === 201
      );
      const relData = await relResponse.json();
      const relationshipId = relData.id;
      expect(relationshipId).toBeTruthy();
      helpers.logStep(`Relationship created with ID: ${relationshipId}`);

      // Step 6: Verify relationship in graph
      await page.waitForTimeout(2000);
      const updatedEdges = await page.locator('[data-testid="graph-edge"]').count();
      expect(updatedEdges).toBe(initialEdges + 1);
      helpers.logStep(`Relationship added: ${updatedEdges} edges`);

      // Step 7: Verify entity details consistency
      await helpers.waitAndClick(`[data-testid="node-${entityId}"]`);
      await helpers.expectElementVisible('[data-testid="entity-details-panel"]');

      const entityName = await helpers.getTextContent('[data-testid="entity-name-detail"]');
      const entityType = await helpers.getTextContent('[data-testid="entity-type-detail"]');
      const entityDescription = await helpers.getTextContent('[data-testid="entity-description-detail"]');

      expect(entityName).toBe('Test Entity E2E');
      expect(entityType).toBe('Person');
      expect(entityDescription).toBe('Test entity for E2E validation');
      helpers.logStep('Entity details verified consistent');

      // Step 8: Verify relationship details
      await helpers.waitAndClick(`[data-testid="edge-${relationshipId}"]`);
      await helpers.expectElementVisible('[data-testid="relationship-details-panel"]');

      const relType = await helpers.getTextContent('[data-testid="relationship-type-detail"]');
      const sourceEntity = await helpers.getTextContent('[data-testid="source-entity-detail"]');
      const targetEntity = await helpers.getTextContent('[data-testid="target-entity-detail"]');

      expect(relType).toBe('WORKS_FOR');
      expect(sourceEntity).toContain('Test Entity E2E');
      expect(targetEntity).toContain('Test Organization');
      helpers.logStep('Relationship details verified consistent');

      // Step 9: Verify graph analytics consistency
      await helpers.waitAndClick('[data-testid="graph-analytics-tab"]');
      await helpers.expectElementVisible('[data-testid="graph-metrics"]');

      const graphDensity = await helpers.getTextContent('[data-testid="graph-density"]');
      const nodeCount = await helpers.getTextContent('[data-testid="node-count"]');
      const edgeCount = await helpers.getTextContent('[data-testid="edge-count"]');

      expect(parseInt(nodeCount)).toBe(updatedNodes);
      expect(parseInt(edgeCount)).toBe(updatedEdges);
      expect(parseFloat(graphDensity)).toBeGreaterThan(0);
      helpers.logStep(`Graph analytics consistent: density ${graphDensity}, ${nodeCount} nodes, ${edgeCount} edges`);
    });

    test('should handle graph data integrity during complex operations', async ({ page }) => {
      helpers.logStep('Testing graph data integrity during complex operations');

      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');

      // Step 1: Perform bulk entity operations
      await helpers.waitAndClick('[data-testid="bulk-operations-tab"]');
      await helpers.expectElementVisible('[data-testid="bulk-operations-panel"]');

      // Import entities from CSV
      await helpers.waitAndClick('[data-testid="import-csv-button"]');
      await helpers.uploadFile('[data-testid="csv-file-input"]', './tests/fixtures/files/test-entities.csv');
      await helpers.waitAndClick('[data-testid="import-entities"]');

      // Monitor import process
      await helpers.expectElementVisible('[data-testid="import-progress"]');
      await helpers.expectElementVisible('[data-testid="import-complete"]');

      const importResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/entities/import') && response.status() === 200
      );
      const importData = await importResponse.json();
      expect(importData.imported_count).toBeGreaterThan(0);
      helpers.logStep(`Imported ${importData.imported_count} entities`);

      // Step 2: Verify graph state after bulk import
      await page.waitForTimeout(3000);
      const postImportNodes = await page.locator('[data-testid="graph-node"]').count();
      expect(postImportNodes).toBeGreaterThan(0);
      helpers.logStep(`Graph state after import: ${postImportNodes} nodes`);

      // Step 3: Perform graph clustering operation
      await helpers.waitAndClick('[data-testid="graph-clustering-tab"]');
      await helpers.expectElementVisible('[data-testid="clustering-controls"]');

      await helpers.selectOption('[data-testid="clustering-algorithm"]', 'louvain');
      await helpers.fillField('[data-testid="resolution-input"]', '1.0');
      await helpers.waitAndClick('[data-testid="run-clustering"]');

      await helpers.expectElementVisible('[data-testid="clustering-progress"]');
      await helpers.expectElementVisible('[data-testid="clustering-complete"]');

      const clusteringResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/graph/cluster') && response.status() === 200
      );
      const clusterData = await clusteringResponse.json();
      expect(clusterData.clusters).toBeDefined();
      expect(clusterData.cluster_count).toBeGreaterThan(0);
      helpers.logStep(`Graph clustered into ${clusterData.cluster_count} communities`);

      // Step 4: Verify cluster assignments are consistent
      await helpers.waitAndClick('[data-testid="cluster-results"]');
      await helpers.expectElementVisible('[data-testid="cluster-list"]');

      const clusters = page.locator('[data-testid="cluster-item"]');
      await expect(clusters).toHaveCount(clusterData.cluster_count);

      let totalClusteredNodes = 0;
      for (let i = 0; i < await clusters.count(); i++) {
        const cluster = clusters.nth(i);
        const clusterSize = await helpers.getTextContent(cluster.locator('[data-testid="cluster-size"]'));
        totalClusteredNodes += parseInt(clusterSize);
      }

      expect(totalClusteredNodes).toBeLessThanOrEqual(postImportNodes);
      helpers.logStep(`Cluster assignment verified: ${totalClusteredNodes} nodes clustered`);

      // Step 5: Perform graph pruning operation
      await helpers.waitAndClick('[data-testid="graph-pruning-tab"]');
      await helpers.expectElementVisible('[data-testid="pruning-controls"]');

      await helpers.fillField('[data-testid="min-degree-input"]', '2');
      await helpers.fillField('[data-testid="min-weight-input"]', '0.1');
      await helpers.waitAndClick('[data-testid="run-pruning"]');

      await helpers.expectElementVisible('[data-testid="pruning-progress"]');
      await helpers.expectElementVisible('[data-testid="pruning-complete"]');

      const pruningResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/graph/prune') && response.status() === 200
      );
      const pruneData = await pruningResponse.json();
      expect(pruneData.removed_nodes).toBeDefined();
      expect(pruneData.removed_edges).toBeDefined();
      helpers.logStep(`Graph pruned: removed ${pruneData.removed_nodes} nodes, ${pruneData.removed_edges} edges`);

      // Step 6: Verify final graph integrity
      const finalNodes = await page.locator('[data-testid="graph-node"]').count();
      const finalEdges = await page.locator('[data-testid="graph-edge"]').count();

      expect(finalNodes).toBe(postImportNodes - pruneData.removed_nodes);
      expect(finalEdges).toBeGreaterThanOrEqual(0);
      helpers.logStep(`Final graph state: ${finalNodes} nodes, ${finalEdges} edges`);

      // Step 7: Verify graph analytics consistency
      await helpers.waitAndClick('[data-testid="graph-analytics-tab"]');
      const finalDensity = await helpers.getTextContent('[data-testid="graph-density"]');
      const finalNodeCount = await helpers.getTextContent('[data-testid="node-count"]');
      const finalEdgeCount = await helpers.getTextContent('[data-testid="edge-count"]');

      expect(parseInt(finalNodeCount)).toBe(finalNodes);
      expect(parseInt(finalEdgeCount)).toBe(finalEdges);
      helpers.logStep(`Final analytics verified: density ${finalDensity}`);
    });
  });

  test.describe('Analytics Data Pipeline Integrity', () => {
    test('should maintain analytics data integrity through real-time processing', async ({ page }) => {
      helpers.logStep('Testing analytics data pipeline integrity');

      // Step 1: Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      await page.waitForTimeout(3000);

      // Step 2: Capture initial analytics state
      const initialMetrics = await page.evaluate(() => {
        const cards = document.querySelectorAll('[data-testid="metric-card"]');
        return Array.from(cards).map(card => ({
          name: card.querySelector('[data-testid="metric-name"]')?.textContent,
          value: card.querySelector('[data-testid="metric-value"]')?.textContent,
        }));
      });

      helpers.logStep(`Initial analytics state: ${initialMetrics.length} metrics`);

      // Step 3: Trigger data update event
      await helpers.waitAndClick('[data-testid="trigger-data-update"]');
      await page.waitForTimeout(2000);

      // Step 4: Verify data update propagation
      const updatedMetrics = await page.evaluate(() => {
        const cards = document.querySelectorAll('[data-testid="metric-card"]');
        return Array.from(cards).map(card => ({
          name: card.querySelector('[data-testid="metric-name"]')?.textContent,
          value: card.querySelector('[data-testid="metric-value"]')?.textContent,
        }));
      });

      expect(updatedMetrics).toHaveLength(initialMetrics.length);
      helpers.logStep(`Updated analytics state: ${updatedMetrics.length} metrics`);

      // Step 5: Verify real-time data consistency
      const realtimeResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/analytics/realtime') && response.status() === 200
      );
      const realtimeData = await realtimeResponse.json();
      expect(realtimeData.metrics).toBeDefined();
      expect(realtimeData.timestamp).toBeTruthy();
      helpers.logStep(`Real-time data received at ${realtimeData.timestamp}`);

      // Step 6: Test analytics aggregation consistency
      await helpers.waitAndClick('[data-testid="analytics-aggregation-tab"]');
      await helpers.expectElementVisible('[data-testid="aggregation-controls"]');

      await helpers.selectOption('[data-testid="time-range"]', '1h');
      await helpers.selectOption('[data-testid="aggregation-function"]', 'avg');
      await helpers.waitAndClick('[data-testid="run-aggregation"]');

      const aggregationResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/analytics/aggregate') && response.status() === 200
      );
      const aggregationData = await aggregationResponse.json();
      expect(aggregationData.aggregated_values).toBeDefined();
      expect(aggregationData.sample_count).toBeGreaterThan(0);
      helpers.logStep(`Aggregation completed: ${aggregationData.sample_count} samples`);

      // Step 7: Verify data pipeline consistency checks
      await helpers.waitAndClick('[data-testid="data-pipeline-tab"]');
      await helpers.expectElementVisible('[data-testid="pipeline-status"]');

      const pipelineStatus = await helpers.getTextContent('[data-testid="pipeline-status"]');
      expect(pipelineStatus).toContain('healthy');

      const dataLatency = await helpers.getTextContent('[data-testid="data-latency"]');
      expect(parseFloat(dataLatency)).toBeLessThan(5000); // Less than 5 seconds
      helpers.logStep(`Data pipeline status: ${pipelineStatus}, latency: ${dataLatency}`);

      // Step 8: Verify end-to-end data consistency
      await helpers.waitAndClick('[data-testid="consistency-check"]');
      await helpers.expectElementVisible('[data-testid="consistency-results"]');

      const consistencyScore = await helpers.getTextContent('[data-testid="consistency-score"]');
      expect(parseFloat(consistencyScore)).toBeGreaterThan(0.95);
      helpers.logStep(`Data consistency score: ${consistencyScore}`);
    });

    test('should handle analytics data corruption and recovery', async ({ page }) => {
      helpers.logStep('Testing analytics data corruption and recovery');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Step 1: Simulate data corruption
      await helpers.waitAndClick('[data-testid="simulate-corruption"]');
      await page.waitForTimeout(2000);

      // Step 2: Verify corruption detection
      await helpers.expectElementVisible('[data-testid="corruption-detected"]');
      const corruptionAlert = await helpers.getTextContent('[data-testid="corruption-alert"]');
      expect(corruptionAlert).toContain('data inconsistency');
      helpers.logStep('Data corruption detected');

      // Step 3: Verify automatic recovery process
      await helpers.expectElementVisible('[data-testid="recovery-process"]');
      await helpers.expectElementVisible('[data-testid="recovery-progress"]');

      await helpers.expectElementVisible('[data-testid="recovery-complete"]', { timeout: 30000 });
      helpers.logStep('Automatic recovery completed');

      // Step 4: Verify data restoration
      const recoveryResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/analytics/restore') && response.status() === 200
      );
      const recoveryData = await recoveryResponse.json();
      expect(recoveryData.restored).toBe(true);
      expect(recoveryData.restored_records).toBeGreaterThan(0);
      helpers.logStep(`Data restored: ${recoveryData.restored_records} records`);

      // Step 5: Verify data integrity post-recovery
      await helpers.waitAndClick('[data-testid="verify-integrity"]');
      await helpers.expectElementVisible('[data-testid="integrity-results"]');

      const integrityScore = await helpers.getTextContent('[data-testid="integrity-score"]');
      expect(parseFloat(integrityScore)).toBeGreaterThan(0.98);
      helpers.logStep(`Data integrity verified: ${integrityScore}`);

      // Step 6: Verify analytics functionality restored
      await helpers.waitAndClick('[data-testid="refresh-analytics"]');
      await helpers.expectElementVisible('[data-testid="metric-card"]');

      const restoredMetrics = page.locator('[data-testid="metric-card"]');
      await expect(restoredMetrics).toHaveCount.greaterThan(0);
      helpers.logStep('Analytics functionality restored');
    });
  });

  test.describe('Cross-System Data Validation', () => {
    test('should validate data consistency across system boundaries', async ({ page }) => {
      helpers.logStep('Testing cross-system data validation');

      // Step 1: Create test data in one system
      await helpers.waitAndClick('[data-testid="documents-nav-link"]');
      await helpers.uploadFile('[data-testid="file-input"]', './tests/fixtures/files/sample-document.pdf');
      await helpers.waitAndClick('[data-testid="upload-button"]');

      const uploadResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/documents/upload') && response.status() === 201
      );
      const documentData = await uploadResponse.json();
      const documentId = documentData.id;

      await helpers.expectElementVisible('[data-testid="processing-complete"]', { timeout: 30000 });
      helpers.logStep(`Document created: ${documentId}`);

      // Step 2: Verify data appears in knowledge graph
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await page.waitForTimeout(3000);

      const graphNodes = page.locator('[data-testid="graph-node"]');
      const documentNode = graphNodes.filter({ hasText: new RegExp(documentId) });
      await expect(documentNode).toHaveCount(1);
      helpers.logStep('Document entity found in knowledge graph');

      // Step 3: Verify data appears in analytics
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await page.waitForTimeout(3000);

      const analyticsMetrics = page.locator('[data-testid="metric-card"]');
      const documentMetric = analyticsMetrics.filter({ hasText: /document/i });
      await expect(documentMetric).toHaveCount.greaterThan(0);
      helpers.logStep('Document metrics found in analytics');

      // Step 4: Verify data consistency across systems
      await helpers.waitAndClick('[data-testid="cross-system-validation"]');
      await helpers.expectElementVisible('[data-testid="validation-results"]');

      const validationResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/validate/cross-system') && response.status() === 200
      );
      const validationData = await validationResponse.json();
      expect(validationData.consistent).toBe(true);
      expect(validationData.systems_included).toContain('documents');
      expect(validationData.systems_included).toContain('knowledge_graph');
      expect(validationData.systems_included).toContain('analytics');
      helpers.logStep('Cross-system validation passed');

      // Step 5: Test data synchronization
      await helpers.waitAndClick('[data-testid="sync-data"]');
      await helpers.expectElementVisible('[data-testid="sync-progress"]');

      const syncResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/sync/all') && response.status() === 200
      );
      const syncData = await syncResponse.json();
      expect(syncData.synced).toBe(true);
      expect(syncData.records_synced).toBeGreaterThan(0);
      helpers.logStep(`Data synchronized: ${syncData.records_synced} records`);

      // Step 6: Verify data consistency after sync
      await helpers.waitAndClick('[data-testid="post-sync-validation"]');
      await helpers.expectElementVisible('[data-testid="post-sync-results"]');

      const postSyncScore = await helpers.getTextContent('[data-testid="consistency-score"]');
      expect(parseFloat(postSyncScore)).toBe(1.0); // Perfect consistency
      helpers.logStep(`Post-sync consistency: ${postSyncScore}`);
    });

    test('should handle distributed transaction consistency', async ({ page }) => {
      helpers.logStep('Testing distributed transaction consistency');

      // Step 1: Initiate distributed transaction
      await helpers.waitAndClick('[data-testid="distributed-operations-tab"]');
      await helpers.expectElementVisible('[data-testid="distributed-controls"]');

      await helpers.waitAndClick('[data-testid="start-distributed-transaction"]');
      await helpers.expectElementVisible('[data-testid="transaction-id"]');

      const transactionId = await helpers.getTextContent('[data-testid="transaction-id"]');
      expect(transactionId).toBeTruthy();
      helpers.logStep(`Distributed transaction started: ${transactionId}`);

      // Step 2: Perform multiple operations in transaction
      // Operation 1: Create document
      await helpers.waitAndClick('[data-testid="op-create-document"]');
      await helpers.uploadFile('[data-testid="tx-file-input"]', './tests/fixtures/files/tx-test.pdf');
      await helpers.waitAndClick('[data-testid="add-to-transaction"]');

      // Operation 2: Create entity
      await helpers.waitAndClick('[data-testid="op-create-entity"]');
      await helpers.fillField('[data-testid="tx-entity-name"]', 'TX Test Entity');
      await helpers.waitAndClick('[data-testid="add-to-transaction"]');

      // Operation 3: Create relationship
      await helpers.waitAndClick('[data-testid="op-create-relationship"]');
      await helpers.waitAndClick('[data-testid="add-to-transaction"]');

      const transactionOperations = await page.locator('[data-testid="transaction-operation"]').count();
      expect(transactionOperations).toBe(3);
      helpers.logStep(`Added ${transactionOperations} operations to transaction`);

      // Step 3: Commit transaction
      await helpers.waitAndClick('[data-testid="commit-transaction"]');
      await helpers.expectElementVisible('[data-testid="commit-progress"]');

      const commitResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/transactions/commit') && response.status() === 200
      );
      const commitData = await commitResponse.json();
      expect(commitData.committed).toBe(true);
      expect(commitData.operations_successful).toBe(3);
      helpers.logStep('Transaction committed successfully');

      // Step 4: Verify ACID properties
      await helpers.waitAndClick('[data-testid="verify-acid-properties"]');
      await helpers.expectElementVisible('[data-testid="acid-results"]');

      const atomicity = await helpers.getTextContent('[data-testid="atomicity-result"]');
      const consistency = await helpers.getTextContent('[data-testid="consistency-result"]');
      const isolation = await helpers.getTextContent('[data-testid="isolation-result"]');
      const durability = await helpers.getTextContent('[data-testid="durability-result"]');

      expect(atomicity).toContain('passed');
      expect(consistency).toContain('passed');
      expect(isolation).toContain('passed');
      expect(durability).toContain('passed');
      helpers.logStep('ACID properties verified');

      // Step 5: Test transaction rollback (rollback scenario)
      await helpers.waitAndClick('[data-testid="start-new-transaction"]');
      await helpers.waitAndClick('[data-testid="op-failing-operation"]');
      await helpers.waitAndClick('[data-testid="add-to-transaction"]');
      await helpers.waitAndClick('[data-testid="rollback-transaction"]');

      const rollbackResponse = await page.waitForResponse(response =>
        response.url().includes('/api/v1/transactions/rollback') && response.status() === 200
      );
      const rollbackData = await rollbackResponse.json();
      expect(rollbackData.rolled_back).toBe(true);
      helpers.logStep('Transaction rollback successful');

      // Step 6: Verify rollback consistency
      await helpers.waitAndClick('[data-testid="verify-rollback"]');
      await helpers.expectElementVisible('[data-testid="rollback-results"]');

      const rollbackConsistency = await helpers.getTextContent('[data-testid="rollback-consistency"]');
      expect(rollbackConsistency).toContain('passed');
      helpers.logStep('Rollback consistency verified');
    });
  });
});
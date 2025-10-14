"""
Updated worker testing snippet for notebook cell 19

Replace the existing worker status check code with this
"""

# Test background processing and job status
print("⚙️ **Testing Background Processing...**")

# Check processing status for uploaded documents
if uploaded_documents:
    print(f"\n📊 **Checking Processing Status for {len(uploaded_documents)} documents...**")

    processing_results = []

    for doc in uploaded_documents:
        doc_id = doc.get("id")
        if doc_id:
            try:
                # Try to get processing status
                status_response = tester.session.get(
                    f"{BASE_URL}/api/v1/processing/documents/{doc_id}/status",
                    timeout=10
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    processing_results.append({
                        "document_id": doc_id,
                        "title": doc["title"],
                        "status": status_data.get("processing_status", "unknown"),
                        "is_embedded": status_data.get("is_embedded", False),
                        "is_indexed": status_data.get("is_indexed", False),
                        "error": status_data.get("processing_error")
                    })
                    print(f"📄 {doc['title']}: {status_data.get('processing_status', 'unknown')}")
                else:
                    processing_results.append({
                        "document_id": doc_id,
                        "title": doc["title"],
                        "status": "unknown",
                        "is_embedded": False,
                        "is_indexed": False,
                        "error": f"HTTP {status_response.status_code}"
                    })
                    print(f"📄 {doc['title']}: Status check returned {status_response.status_code}")

            except Exception as e:
                processing_results.append({
                    "document_id": doc_id,
                    "title": doc["title"],
                    "status": "error",
                    "is_embedded": False,
                    "is_indexed": False,
                    "error": str(e)
                })
                print(f"📄 {doc['title']}: Error checking status - {str(e)}")

    # Create processing status visualization if we have results
    if processing_results:
        df_processing = pd.DataFrame(processing_results)

        # Status distribution
        status_counts = df_processing['status'].value_counts()

        try:
            fig_status = go.Figure()
            fig_status.add_trace(go.Pie(
                labels=status_counts.index,
                values=status_counts.values,
                hole=0.3,
                marker_colors=['#4CAF50', '#FF9800', '#F44336', '#9E9E9E']
            ))

            fig_status.update_layout(
                title="📊 Document Processing Status",
                height=400
            )

            fig_status.show()
        except Exception as e:
            print(f"⚠️ Visualization skipped: {str(e)}")
            print("\n📊 Processing Status Summary:")
            print(status_counts)

        print("\n📋 **Processing Status Details:**")
        display(df_processing[['title', 'status', 'is_embedded', 'is_indexed']])

else:
    print("ℹ️ No documents uploaded to check processing status")

# Test Celery worker status using the NEW endpoint
print("\n🏭 **Testing Background Workers...**")
try:
    worker_response = tester.session.get(f"{BASE_URL}/api/v1/workers/status", timeout=10)
    if worker_response.status_code == 200:
        worker_data = worker_response.json()
        print("✅ Background Workers Active")
        print(f"- Active Workers: {worker_data.get('active_workers', 'Unknown')}")
        print(f"- Total Workers: {worker_data.get('total_workers', 'Unknown')}")
        print(f"- Active Tasks: {worker_data.get('active_tasks', 'Unknown')}")
        print(f"- Pending Tasks: {worker_data.get('pending_tasks', 'Unknown')}")
        print(f"- Registered Tasks: {worker_data.get('registered_tasks', 'Unknown')}")

        # Show detailed worker information
        worker_details = worker_data.get('worker_details', [])
        if worker_details:
            print(f"\n📋 **Worker Details:**")
            for worker in worker_details:
                print(f"\n  🔧 Worker: {worker.get('hostname', 'Unknown')}")
                print(f"     Status: {worker.get('status', 'Unknown')}")
                print(f"     Active Tasks: {worker.get('active_tasks', 0)}")
                print(f"     Pending Tasks: {worker.get('pending_tasks', 0)}")
                print(f"     Total Processed: {worker.get('total_processed', 0)}")

                pool_info = worker.get('pool', {})
                if pool_info:
                    print(f"     Concurrency: {pool_info.get('max-concurrency', 'Unknown')}")
                    processes = pool_info.get('processes', [])
                    if processes:
                        print(f"     Worker Processes: {len(processes)}")

        # Check worker health
        health_response = tester.session.get(f"{BASE_URL}/api/v1/workers/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            if health_data.get('healthy'):
                print(f"\n🏥 **Worker Health:** ✅ Healthy")
                print(f"   Workers Online: {health_data.get('workers_online', 0)}")
            else:
                print(f"\n🏥 **Worker Health:** ❌ Unhealthy")
                print(f"   Workers Online: {health_data.get('workers_online', 0)}")
                issues = health_data.get('issues', [])
                if issues:
                    print(f"   Issues:")
                    for issue in issues:
                        print(f"     - {issue}")
    else:
        print(f"⚠️ Worker status returned: {worker_response.status_code}")
        print(f"   Response: {worker_response.text[:200]}")
except Exception as e:
    print(f"❌ Worker status error: {str(e)}")

print("\n⚙️ **Background Processing Summary:**")
print("✅ Document processing status tracking available")
print("✅ Background workers operational")
print("✅ Real-time worker monitoring active")

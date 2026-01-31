# CI/CD Setup - TODO

## ✅ Done Today (Jan 31)
- [x] Removed depot.dev from CI workflows
- [x] Updated `test-pipeline.yml` (uses docker/build-push-action)
- [x] Updated `docker-build.yml` (uses docker/build-push-action)
- [x] Created `deploy.yml` for DigitalOcean Kubernetes
- [x] Updated workflows README
- [x] Installed Serena MCP for code navigation
- [x] Imported databases (Postgres, Neo4j, Qdrant)

## 📋 TODO Tomorrow
1. **Add GitHub Secret:**
   ```
   DIGITALOCEAN_ACCESS_TOKEN = <your DO API token>
   ```

2. **Update cluster name in `.github/workflows/deploy.yml`:**
   ```yaml
   CLUSTER_NAME: <your-actual-cluster-name>
   ```

3. **Create K8s namespaces:**
   ```bash
   doctl kubernetes cluster kubeconfig save <cluster-name>
   kubectl create namespace rag-staging
   kubectl create namespace rag-production
   ```

4. **Optional: GitHub Environments**
   - Settings → Environments → Create `staging` + `production`
   - Add required reviewers for production

5. **Test the pipeline:**
   - Push to a feature branch
   - Open PR to `develop` or `main`
   - Watch Actions tab

## 🔗 Quick Commands
```bash
# Get your DO cluster name
doctl kubernetes cluster list

# Get your DO API token (create new one)
# https://cloud.digitalocean.com/account/api/tokens

# SSH to server
ssh clawdbot@138.197.36.44
```

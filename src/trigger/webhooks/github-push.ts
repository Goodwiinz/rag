import { logger, task, metadata } from "@trigger.dev/sdk";
import { backendClient } from "../_lib/backend-client";

const DOCUMENT_EXTENSIONS = new Set([
  ".md",
  ".pdf",
  ".txt",
  ".rst",
  ".csv",
  ".json",
  ".yaml",
  ".yml",
]);

function isDocumentFile(path: string): boolean {
  const ext = path.slice(path.lastIndexOf(".")).toLowerCase();
  return DOCUMENT_EXTENSIONS.has(ext);
}

interface GitHubPushPayload {
  repository: {
    full_name: string;
    html_url: string;
    default_branch: string;
  };
  ref: string;
  commits: Array<{
    id: string;
    message: string;
    added: string[];
    modified: string[];
    removed: string[];
  }>;
  sender: {
    login: string;
  };
}

export const githubPushReindex = task({
  id: "github-push-reindex",
  maxDuration: 1800,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 30000,
    factor: 2,
  },
  run: async (payload: GitHubPushPayload) => {
    const { repository, ref, commits } = payload;

    logger.info("Processing GitHub push event", {
      repo: repository.full_name,
      ref,
      commitCount: commits.length,
    });

    metadata.set("status", "analyzing");
    metadata.set("repo", repository.full_name);

    const changedFiles = new Set<string>();
    const removedFiles = new Set<string>();

    for (const commit of commits) {
      for (const file of commit.added) {
        if (isDocumentFile(file)) changedFiles.add(file);
      }
      for (const file of commit.modified) {
        if (isDocumentFile(file)) changedFiles.add(file);
      }
      for (const file of commit.removed) {
        if (isDocumentFile(file)) {
          removedFiles.add(file);
          changedFiles.delete(file);
        }
      }
    }

    if (changedFiles.size === 0 && removedFiles.size === 0) {
      logger.info("No document files changed in push");
      return { status: "skipped", reason: "no_document_files" };
    }

    metadata.set("status", "processing");
    metadata.set("changedFiles", changedFiles.size);
    metadata.set("removedFiles", removedFiles.size);

    let processed = 0;
    let failed = 0;
    const errors: Array<{ file: string; error: string }> = [];

    for (const file of changedFiles) {
      try {
        const rawUrl = `${repository.html_url}/raw/${ref.replace("refs/heads/", "")}/${file}`;

        await backendClient.post("/api/v2/documents/upload/single", {
          source_url: rawUrl,
          source_type: "github",
          title: file.split("/").pop(),
          metadata: {
            repository: repository.full_name,
            ref,
            path: file,
          },
        });

        processed++;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        errors.push({ file, error: message });
        failed++;
        logger.warn("Failed to process file from push", {
          file,
          error: message,
        });
      }
    }

    metadata.set("status", "completed");

    logger.info("GitHub push processing complete", {
      processed,
      failed,
      removed: removedFiles.size,
    });

    return {
      status: "completed",
      processed,
      failed,
      removed: removedFiles.size,
      errors,
    };
  },
});

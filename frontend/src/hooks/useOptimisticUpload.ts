import { documentService } from "@/services/documentService";
import { Document } from "@/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface OptimisticDocument extends Partial<Document> {
  id: string;
  filename: string;
  status: "uploading" | "processing" | "completed" | "failed";
  progress: number;
  isOptimistic: true;
}

export function useOptimisticUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      // Create a wrapper for progress that matches the signature expected by useMutation
      // but calling documentService.uploadFile which expects (file, onProgress)
      return documentService.uploadFile(file, (progress) => {
        // Update optimistic document progress
        queryClient.setQueryData<Document[]>(["documents"], (old) =>
          old?.map((doc) =>
            doc.id === file.name // Use filename as temp ID
              ? { ...doc, progress }
              : doc
          )
        );
      });
    },

    onMutate: async (file: File) => {
      // Cancel outgoing queries
      await queryClient.cancelQueries({ queryKey: ["documents"] });

      // Snapshot current state
      const previousDocuments = queryClient.getQueryData<Document[]>([
        "documents",
      ]);

      // Create optimistic document
      const optimisticDoc: OptimisticDocument = {
        id: file.name, // Temporary ID
        filename: file.name,
        title: file.name.replace(/\.[^/.]+$/, ""),
        file_type: file.type.split('/')[1] as any, // Simple mapping for now
        file_size: file.size,
        status: "uploading",
        progress: 0,
        upload_timestamp: new Date().toISOString(),
        isOptimistic: true,
      };

      // Add optimistic document to cache
      queryClient.setQueryData<Document[]>(["documents"], (old) => [
        optimisticDoc as Document,
        ...(old || []),
      ]);

      return { previousDocuments, optimisticId: file.name };
    },

    onSuccess: (data, file, context) => {
      // Replace optimistic document with real one
      queryClient.setQueryData<Document[]>(["documents"], (old) =>
        old?.map((doc) =>
          doc.id === context?.optimisticId ? { ...data.data, isOptimistic: false } : doc
        )
      );
    },

    onError: (error, file, context) => {
      // Mark optimistic document as failed
      queryClient.setQueryData<Document[]>(["documents"], (old) =>
        old?.map((doc) =>
          doc.id === context?.optimisticId
            ? { ...doc, status: "failed", error: error.message }
            : doc
        )
      );

      // Optionally revert after delay
      setTimeout(() => {
        queryClient.setQueryData<Document[]>(
          ["documents"],
          context?.previousDocuments
        );
      }, 5000);
    },

    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import * as React from "react";

interface ConfirmDialogProps {
  trigger: React.ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void;
  onCancel?: () => void;
}

export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [open, setOpen] = React.useState(false);

  const handleConfirm = () => {
    onConfirm();
    setOpen(false);
  };

  const handleCancel = () => {
    onCancel?.();
    setOpen(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-[var(--terminal-text-muted)] font-mono text-xs">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel 
            onClick={handleCancel}
            className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] text-[var(--terminal-text-muted)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)] font-mono text-xs uppercase tracking-wider"
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={cn(
              "font-mono text-xs uppercase tracking-wider border transition-all",
              variant === "destructive" 
                ? "bg-red-500/10 border-red-500/50 text-red-400 hover:bg-red-500/20 hover:border-red-500"
                : "bg-[var(--phosphor-green)]/10 border-[var(--phosphor-green)]/50 text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/20 hover:border-[var(--phosphor-green)]"
            )}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Convenience wrapper for delete actions
export function DeleteConfirmDialog({
  itemName,
  onConfirm,
  children,
}: {
  itemName: string;
  onConfirm: () => void;
  children: React.ReactNode;
}) {
  return (
    <ConfirmDialog
      trigger={children}
      title={`Delete ${itemName}?`}
      description={`This action cannot be undone. This will permanently delete the ${itemName}.`}
      confirmLabel="Delete"
      variant="destructive"
      onConfirm={onConfirm}
    />
  );
}

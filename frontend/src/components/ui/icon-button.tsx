import { Button, ButtonProps } from "@/components/ui/button";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import * as React from "react";

export interface IconButtonProps extends Omit<ButtonProps, "children"> {
  /** The icon to display */
  icon: React.ReactNode;
  /** Accessible label (required) - shown to screen readers and in tooltip */
  label: string;
  /** Whether to show tooltip on hover (default: true) */
  showTooltip?: boolean;
  /** Tooltip placement */
  tooltipSide?: "top" | "right" | "bottom" | "left";
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      label,
      showTooltip = true,
      tooltipSide = "top",
      className,
      variant = "ghost",
      size = "icon",
      ...props
    },
    ref
  ) => {
    const button = (
      <Button
        ref={ref}
        variant={variant}
        size={size}
        aria-label={label}
        className={cn("shrink-0", className)}
        {...props}
      >
        {icon}
        <span className="sr-only">{label}</span>
      </Button>
    );

    if (!showTooltip) {
      return button;
    }

    return (
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>{button}</TooltipTrigger>
          <TooltipContent side={tooltipSide}>
            <p className="text-xs">{label}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
);

IconButton.displayName = "IconButton";

// Export convenient size presets
export const IconButtonSm = React.forwardRef<
  HTMLButtonElement,
  IconButtonProps
>((props, ref) => (
  <IconButton ref={ref} className="h-7 w-7" {...props} />
));
IconButtonSm.displayName = "IconButtonSm";

export const IconButtonLg = React.forwardRef<
  HTMLButtonElement,
  IconButtonProps
>((props, ref) => (
  <IconButton ref={ref} className="h-10 w-10" {...props} />
));
IconButtonLg.displayName = "IconButtonLg";

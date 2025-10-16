import React, { useState, useRef, useEffect } from 'react';
import { ChevronDownIcon, CheckIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

export interface SelectProps {
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
  children?: React.ReactNode;
}

const Select = ({ value, onValueChange, disabled, error, children }: SelectProps) => {
  return (
    <SelectContextProvider value={{ value, onValueChange, disabled, error }}>
      {children}
    </SelectContextProvider>
  );
};

interface SelectContextValue {
  value?: string;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
  isOpen?: boolean;
  setIsOpen?: (open: boolean) => void;
}

const SelectContext = React.createContext<SelectContextValue>({});

const SelectContextProvider: React.FC<{ value: SelectContextValue; children: React.ReactNode }> = ({ value, children }) => (
  <SelectContext.Provider value={value}>{children}</SelectContext.Provider>
);

const useSelectContext = () => React.useContext(SelectContext);

export const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { placeholder?: string }
>(({ className, children, placeholder = 'Select...', ...props }, ref) => {
  const { value, disabled, error, isOpen, setIsOpen } = useSelectContext();
  const [displayValue, setDisplayValue] = useState(placeholder);

  // Update display value when selection changes
  useEffect(() => {
    if (value && isOpen !== undefined) {
      // Find the option with matching value
      const optionElements = document.querySelectorAll('[data-select-value]');
      for (const option of optionElements) {
        if (option.getAttribute('data-select-value') === value) {
          setDisplayValue(option.textContent || placeholder);
          break;
        }
      }
    }
  }, [value, placeholder]);

  return (
    <button
      type="button"
      ref={ref}
      onClick={() => setIsOpen?.(!isOpen)}
      className={cn(
        "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background",
        "placeholder:text-muted-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        error && "border-destructive",
        className
      )}
      disabled={disabled}
      {...props}
    >
      <span className={cn("truncate", !value && "text-muted-foreground")}>
        {children || displayValue}
      </span>
      <ChevronDownIcon
        className={cn(
          "h-4 w-4 transition-transform",
          isOpen && "rotate-180"
        )}
      />
    </button>
  );
});

SelectTrigger.displayName = 'SelectTrigger';

export const SelectValue = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement> & { placeholder?: string }
>(({ className, placeholder, ...props }, ref) => {
  const { value } = useSelectContext();

  // This component typically just renders as a placeholder for the selected value
  return (
    <span ref={ref} className={cn("block truncate", className)} {...props}>
      {!value && placeholder}
    </span>
  );
});

SelectValue.displayName = 'SelectValue';

export const SelectContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { isOpen, setIsOpen } = useSelectContext();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen?.(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, setIsOpen]);

  if (!isOpen) return null;

  return (
    <div
      ref={containerRef}
      className={cn(
        "absolute top-full left-0 right-0 z-50 mt-1 max-h-60 overflow-auto rounded-md border border-input bg-popover shadow-md",
        className
      )}
      {...props}
    >
      <div className="p-1">{children}</div>
    </div>
  );
});

SelectContent.displayName = 'SelectContent';

export interface SelectItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export const SelectItem = React.forwardRef<HTMLButtonElement, SelectItemProps>(
  ({ className, children, value, ...props }, ref) => {
    const { value: selectedValue, onValueChange, setIsOpen } = useSelectContext();

    const handleSelect = () => {
      onValueChange?.(value);
      setIsOpen?.(false);
    };

    return (
      <button
        ref={ref}
        type="button"
        onClick={handleSelect}
        data-select-value={value}
        className={cn(
          "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 px-2 text-sm outline-none",
          "hover:bg-accent hover:text-accent-foreground",
          "focus:bg-accent focus:text-accent-foreground",
          selectedValue === value && "bg-accent text-accent-foreground",
          className
        )}
        {...props}
      >
        <span className="truncate">{children}</span>
        {selectedValue === value && (
          <CheckIcon className="ml-auto h-4 w-4" />
        )}
      </button>
    );
  }
);

SelectItem.displayName = 'SelectItem';

export { Select };
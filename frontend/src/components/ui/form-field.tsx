import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import * as React from 'react';

export interface FormFieldProps extends React.ComponentProps<'input'> {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  showValidIcon?: boolean;
  validate?: (value: string) => string | undefined;
}

export const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(
  (
    {
      label,
      error,
      hint,
      required,
      showValidIcon = true,
      validate,
      className,
      id,
      onChange,
      onBlur,
      ...props
    },
    ref
  ) => {
    const [touched, setTouched] = React.useState(false);
    const [internalError, setInternalError] = React.useState<string>();
    const generatedId = React.useId();
    const fieldId = id || generatedId;
    const errorId = `${fieldId}-error`;
    const hintId = `${fieldId}-hint`;

    const displayError = error || (touched ? internalError : undefined);
    const isValid =
      touched &&
      !displayError &&
      props.value !== undefined &&
      props.value !== '';

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setTouched(true);
      if (validate) {
        setInternalError(validate(e.target.value));
      }
      onBlur?.(e);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (touched && validate) {
        setInternalError(validate(e.target.value));
      }
      onChange?.(e);
    };

    return (
      <div className="space-y-2">
        <Label
          htmlFor={fieldId}
          className={cn(displayError && 'text-destructive')}
        >
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>

        <div className="relative">
          <Input
            ref={ref}
            id={fieldId}
            aria-invalid={!!displayError}
            aria-describedby={cn(displayError && errorId, hint && hintId)}
            className={cn(
              'pr-10',
              displayError &&
                'border-destructive focus-visible:ring-destructive',
              isValid &&
                'border-[var(--nous-terra)] focus-visible:ring-[var(--nous-terra)]',
              className
            )}
            onBlur={handleBlur}
            onChange={handleChange}
            {...props}
          />

          {/* Validation indicator */}
          {showValidIcon && touched && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              {displayError ? (
                <AlertCircle className="h-4 w-4 text-destructive" />
              ) : isValid ? (
                <CheckCircle2 className="h-4 w-4 text-[var(--nous-terra)]" />
              ) : null}
            </div>
          )}
        </div>

        {/* Error message */}
        {displayError && (
          <p
            id={errorId}
            className="text-xs text-destructive flex items-center gap-1"
            role="alert"
          >
            <AlertCircle className="h-3 w-3" />
            {displayError}
          </p>
        )}

        {/* Hint text */}
        {hint && !displayError && (
          <p id={hintId} className="text-xs text-muted-foreground">
            {hint}
          </p>
        )}
      </div>
    );
  }
);

FormField.displayName = 'FormField';

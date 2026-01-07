export const validators = {
  required: (message = "This field is required") => (value: string) =>
    !value?.trim() ? message : undefined,

  minLength: (min: number, message?: string) => (value: string) =>
    value && value.length < min
      ? message || `Must be at least ${min} characters`
      : undefined,

  maxLength: (max: number, message?: string) => (value: string) =>
    value && value.length > max
      ? message || `Must be no more than ${max} characters`
      : undefined,

  email: (message = "Invalid email address") => (value: string) =>
    value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? message : undefined,

  url: (message = "Invalid URL") => (value: string) => {
    if (!value) return undefined;
    try {
      new URL(value);
      return undefined;
    } catch {
      return message;
    }
  },

  pattern: (regex: RegExp, message: string) => (value: string) =>
    value && !regex.test(value) ? message : undefined,

  compose:
    (...validators: Array<(value: string) => string | undefined>) =>
    (value: string) => {
      for (const validate of validators) {
        const error = validate(value);
        if (error) return error;
      }
      return undefined;
    },
};

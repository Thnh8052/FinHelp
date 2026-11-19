/** The server's minimum for any new password (backend auth.PASSWORD_MIN_CHARS). */
export const MIN_PASSWORD = 8;

export type PasswordChangeProblem = "currentMissing" | "tooShort" | "mismatch" | "unchanged";

/** What the change-password dialog refuses before sending anything; null when the request may go. Passwords are taken exactly as typed. */
export const passwordChangeProblem = (current: string, next: string, confirm: string): PasswordChangeProblem | null => {
  if (!current) return "currentMissing";
  if (next.length < MIN_PASSWORD) return "tooShort";
  if (next !== confirm) return "mismatch";
  if (next === current) return "unchanged";
  return null;
};

import { MIN_PASSWORD } from "./passwordChange.ts"; // the extension lets the node test script load it (allowImportingTsExtensions)

/** The server's username rule (backend auth.RegisterRequest): 3 to 32 letters without accents, digits, dot, underscore or hyphen. */
export const USERNAME = /^[A-Za-z0-9._-]{3,32}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type SignUpField = "email" | "username" | "password";
export type SignUpProblem = "emailMissing" | "emailInvalid" | "usernameMissing" | "usernameRule" | "passwordMissing" | "passwordShort";

/** What the sign-up form refuses before sending, per field (the message shows under that field). Email and username are trimmed when sent. */
export const signUpProblems = (f: { email: string; username: string; password: string }): Partial<Record<SignUpField, SignUpProblem>> => {
  const out: Partial<Record<SignUpField, SignUpProblem>> = {};
  const email = f.email.trim();
  const username = f.username.trim();
  if (!email) out.email = "emailMissing";
  else if (!EMAIL.test(email)) out.email = "emailInvalid";
  if (!username) out.username = "usernameMissing";
  else if (!USERNAME.test(username)) out.username = "usernameRule";
  if (!f.password) out.password = "passwordMissing";
  else if (f.password.length < MIN_PASSWORD) out.password = "passwordShort";
  return out;
};

/** The live checklist under the password field. */
export const passwordChecks = (password: string): { length: boolean } => ({ length: password.length >= MIN_PASSWORD });

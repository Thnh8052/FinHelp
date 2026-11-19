/** The app draws nothing yet: a session is kept in this browser and its first check has not answered (a member would look like a guest for a
 * moment). Only the first check: a sign-in or sign-up that runs later keeps the page, so the sign-in box can show why it was refused. */
export const waitsForSession = (s: { hasSession: boolean; user: unknown; checkingSession: boolean }): boolean =>
  s.hasSession && !s.user && s.checkingSession;

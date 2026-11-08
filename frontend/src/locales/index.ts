import { en } from "./en";
import { vi } from "./vi";
import { Language, TranslationSchema } from "./types";

export const translations: Record<Language, TranslationSchema> = {
  en,
  vi,
};

export * from "./types";

